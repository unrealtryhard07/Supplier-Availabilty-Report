#!/usr/bin/env python3
"""Generate the Tableau version of the supplier availability report.

Writes tableau/Supplier Availability Report.twb, a workbook that connects to
the published data source "Supplier's Availability Data" on Tableau Cloud and
mirrors the HTML report:

  Report  - page 1: verdict, what we need, key figures, stores, categories,
            restock-first list (one image per supplier)
  Detail  - category x store grid with sub-categories, full out-of-stock list

    python3 tools/build_tableau_workbook.py
"""
import os
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tableau" / "Supplier Availability Report.twb"

# Site details come from the environment so they stay out of this public repo:
#   TABLEAU_SERVER=xxx.online.tableau.com TABLEAU_SITE=yoursite python3 tools/build_tableau_workbook.py
DS = "sqlproxy.0f3kq8s1suppavail7x2m9d4hc1"
SITE = os.environ.get("TABLEAU_SITE", "your-site")
SERVER = os.environ.get("TABLEAU_SERVER", "your-pod.online.tableau.com")
DEFAULT_SUPPLIER = os.environ.get("DEFAULT_SUPPLIER", "")
STORES = ["Egaila", "Hawally", "Jahra", "Salmiya", "Qibla"]

INK, INK2, INK3 = "#0E1A2B", "#46536B", "#6B778F"
CRIT, WARN, GOOD = "#B42318", "#B45309", "#0E6B3B"
CRIT_F, WARN_F, GOOD_F = "#D92D20", "#F5A524", "#16A05A"
BAND = "#0E1A2B"

_uuid = [0]


def uid():
    _uuid[0] += 1
    return "{%08X-0000-4000-8000-%012X}" % (0x5A4B0000 + _uuid[0], _uuid[0])


def a(s):
    """Escape for an XML attribute in single quotes."""
    return escape(s, {"'": "&apos;", '"': "&quot;"})


# --------------------------------------------------------------- fields
BASE = [  # (name, datatype, role, type, aggregation)
    ("Variant ID", "integer", "measure", "quantitative", "Sum"),
    ("Item Code", "string", "dimension", "nominal", "Count"),
    ("Item Name", "string", "dimension", "nominal", "Count"),
    ("Store", "string", "dimension", "nominal", "Count"),
    ("Category", "string", "dimension", "nominal", "Count"),
    ("Sub-Category", "string", "dimension", "nominal", "Count"),
    ("Items in Book", "real", "measure", "quantitative", "Sum"),
    ("Items in Stock", "string", "dimension", "nominal", "Count"),
    ("Current Stock", "real", "measure", "quantitative", "Sum"),
    ("Item Code (Sheet1)", "string", "dimension", "nominal", "Count"),
    ("Category (Sheet1)", "string", "dimension", "nominal", "Count"),
    ("Sub-Category (Sheet1)", "string", "dimension", "nominal", "Count"),
    ("Item Description", "string", "dimension", "nominal", "Count"),
    ("Supplier Account", "integer", "measure", "quantitative", "Sum"),
    ("Supplier Name", "string", "dimension", "nominal", "Count"),
    ("Item Status", "string", "dimension", "nominal", "Count"),
    ("Rank", "string", "dimension", "nominal", "Count"),
]
BASE_REMOTE = {  # remote-type codes used in metadata records
    "integer": 20, "string": 129, "real": 5,
}

P = "[Parameters]"
# Calculated fields: (name, caption, datatype, role, type, formula)
CALCS = [
    ("c_scope", "In report", "boolean", "dimension", "nominal",
     "IFNULL([Rank],'')<>'TD' AND IFNULL([Rank],'')<>'TP/TS' AND NOT ISNULL([Supplier Name]) "
     f"AND ([Store]<>'Qibla' OR {P}.[p_qibla]='Include')"),
    ("c_sup", "Supplier", "string", "dimension", "nominal",
     "{FIXED [Supplier Account]: MIN([Supplier Name])}"),
    ("c_cat", "Category ", "string", "dimension", "nominal", "IFNULL([Category (Sheet1)],'Uncategorised')"),
    ("c_sub", "Sub-category", "string", "dimension", "nominal", "IFNULL([Sub-Category (Sheet1)],'—')"),
    ("c_type", "Type", "string", "dimension", "nominal",
     "CASE [Rank] WHEN 'T1' THEN 'Top seller' WHEN 'T2' THEN 'Strong seller' WHEN 'TN' THEN 'New' ELSE 'Regular' END"),
    ("c_in", "In stock flag", "integer", "measure", "quantitative",
     "IF [c_scope] AND [Items in Stock]='Yes' THEN 1 ELSE 0 END"),
    ("c_one", "Shelf flag", "integer", "measure", "quantitative", "IF [c_scope] THEN 1 ELSE 0 END"),
    ("c_t1", "Top seller shelf", "integer", "measure", "quantitative",
     "IF [c_scope] AND [Rank]='T1' THEN 1 ELSE 0 END"),
    ("c_t1in", "Top seller shelf in stock", "integer", "measure", "quantitative",
     "IF [c_scope] AND [Rank]='T1' AND [Items in Stock]='Yes' THEN 1 ELSE 0 END"),
    ("i_sku", "Product shelves", "integer", "measure", "quantitative",
     "{FIXED [Supplier Account],[Item Code]: SUM([c_one])}"),
    ("i_in", "Product shelves in stock", "integer", "measure", "quantitative",
     "{FIXED [Supplier Account],[Item Code]: SUM([c_in])}"),
    ("i_gap", "Product has a gap", "boolean", "dimension", "nominal", "[i_in]<[i_sku]"),
    ("i_key", "Priority", "string", "dimension", "nominal",
     # Top/strong sellers first, then missing everywhere, then tier, then most stores out.
     "(IF [Rank]='T1' OR [Rank]='T2' THEN '0' ELSE '1' END)"
     "+(IF [i_in]=0 THEN '0' ELSE '1' END)"
     "+(CASE [Rank] WHEN 'T1' THEN '1' WHEN 'T2' THEN '2' WHEN 'T3' THEN '3' WHEN 'T4' THEN '4' "
     "WHEN 'T5' THEN '5' WHEN 'TN' THEN '6' ELSE '7' END)"
     "+STR(9-([i_sku]-[i_in]))+'|'+IFNULL([Item Name],'')"),
    ("i_where", "Where", "string", "dimension", "nominal",
     "IF [i_in]=0 THEN 'Not available in any store' ELSE 'Out of stock in some stores' END"),
    ("i_cell", "cell", "string", "dimension", "nominal",
     "IF [Items in Stock]='Yes' THEN '✓' ELSE 'OUT' END"),
    ("i_out", "cell out", "string", "dimension", "nominal",
     "IF [Items in Stock]='Yes' THEN '' ELSE 'OUT' END"),
    ("i_ok", "cell ok", "string", "dimension", "nominal",
     "IF [Items in Stock]='Yes' THEN '✓' ELSE '' END"),
    # aggregates
    ("m_sku", "Shelves", "integer", "measure", "quantitative", "SUM([c_one])"),
    ("m_in", "Shelves in stock", "integer", "measure", "quantitative", "SUM([c_in])"),
    ("m_out", "Empty shelves", "integer", "measure", "quantitative", "[m_sku]-[m_in]"),
    ("m_pct", "Availability", "real", "measure", "quantitative", "IF [m_sku]>0 THEN [m_in]/[m_sku] END"),
    ("m_pv", "Availability %", "integer", "measure", "quantitative", "INT([m_pct]*100+0.0000001)"),
    ("m_status", "Status", "string", "measure", "nominal",
     f"IF [m_pv]>={P}.[p_target] THEN 'On target' ELSEIF [m_pv]>={P}.[p_critical] THEN 'Below target' ELSE 'Critical' END"),
    ("m_items", "Products", "integer", "measure", "quantitative", "COUNTD(IF [c_scope] THEN [Item Code] END)"),
    ("m_gaps", "Products with gaps", "integer", "measure", "quantitative",
     "COUNTD(IF [c_scope] AND [Items in Stock]<>'Yes' THEN [Item Code] END)"),
    ("m_dead", "Missing everywhere", "integer", "measure", "quantitative",
     "COUNTD(IF [c_scope] AND [i_sku]>0 AND [i_in]=0 THEN [Item Code] END)"),
    ("m_stores", "Stores", "integer", "measure", "quantitative", "COUNTD(IF [c_scope] THEN [Store] END)"),
    ("m_need", "Shelves to refill", "integer", "measure", "quantitative",
     f"MAX(0, INT(CEILING({P}.[p_target]/100*[m_sku]-0.000001))-[m_in])"),
    ("m_t1pct", "Top sellers in stock", "real", "measure", "quantitative",
     "IF SUM([c_t1])>0 THEN SUM([c_t1in])/SUM([c_t1]) END"),
    # text pieces (one per status so each can carry its own colour)
    ("t_name", "Supplier name", "string", "measure", "nominal",
     "IF COUNTD([c_sup])=1 THEN MIN([c_sup]) ELSE STR(COUNTD([c_sup]))+' suppliers' END"),
    ("t_meta", "Header line", "string", "measure", "nominal",
     "'Account '+STR(MIN([Supplier Account]))+'   /   '+STR([m_items])+' products   /   '+STR([m_stores])+' stores'"),
    ("t_date", "Report date", "string", "measure", "nominal",
     "IF [m_sku]>=0 THEN 'REPORT DATE   '+STR(DAY(TODAY()))+' '+LEFT(DATENAME('month',TODAY()),3)+' '+STR(YEAR(TODAY())) END"),
    ("v_crit", "tag crit", "string", "measure", "nominal", "IF [m_status]='Critical' THEN '⊘ CRITICAL' END"),
    ("v_warn", "tag warn", "string", "measure", "nominal", "IF [m_status]='Below target' THEN '▲ BELOW TARGET' END"),
    ("v_good", "tag good", "string", "measure", "nominal", "IF [m_status]='On target' THEN '✔ ON TARGET' END"),
    ("v_text", "Verdict", "string", "measure", "nominal",
     "IF [m_gaps]=0 THEN 'All '+STR([m_items])+' of your products are in stock in every store. Thank you for keeping the shelves full.' "
     "ELSE STR([m_gaps])+' of your '+STR([m_items])+' products are out of stock in at least one store, leaving '"
     "+STR([m_out])+' empty shelves. '"
     f"+(IF [m_need]>0 THEN 'Refill '+STR([m_need])+' to reach the '+STR({P}.[p_target])+'% target.' "
     f"ELSE 'You are above the '+STR({P}.[p_target])+'% target.' END) END"),
    ("v_ask", "Ask", "string", "measure", "nominal",
     f"IF [m_gaps]=0 THEN 'Nothing to restock today.' ELSE 'Please deliver the missing products by '"
     f"+LEFT(DATENAME('weekday',DATEADD('day',{P}.[p_days],TODAY())),3)+' '"
     f"+STR(DAY(DATEADD('day',{P}.[p_days],TODAY())))+' '+LEFT(DATENAME('month',DATEADD('day',{P}.[p_days],TODAY())),3)"
     "+', starting with “Restock these first” below.' END"),
    ("k_crit", "pct crit", "string", "measure", "nominal", "IF [m_status]='Critical' THEN STR([m_pv])+'%' END"),
    ("k_warn", "pct warn", "string", "measure", "nominal", "IF [m_status]='Below target' THEN STR([m_pv])+'%' END"),
    ("k_good", "pct good", "string", "measure", "nominal", "IF [m_status]='On target' THEN STR([m_pv])+'%' END"),
    ("k_gap", "Gap line", "string", "measure", "nominal",
     f"IF [m_pv]>={P}.[p_target] THEN STR([m_pv]-{P}.[p_target])+' pts above the '+STR({P}.[p_target])+'% target' "
     f"ELSE STR({P}.[p_target]-[m_pv])+' pts below the '+STR({P}.[p_target])+'% target' END"),
    ("k_shelves", "Shelves line", "string", "measure", "nominal",
     "STR([m_in])+' of '+STR([m_sku])+' shelves stocked'"),
    ("k_t1", "Top sellers value", "string", "measure", "nominal",
     "IF ISNULL([m_t1pct]) THEN '—' ELSE STR(INT([m_t1pct]*100+0.0000001))+'%' END"),
    ("k_t1sub", "Top sellers sub", "string", "measure", "nominal",
     "IF SUM([c_t1])=0 THEN 'No top sellers listed' ELSE STR(SUM([c_t1in]))+' of '+STR(SUM([c_t1]))+' shelves stocked' END"),
    ("b_lbl", "Bar label", "string", "measure", "nominal",
     "STR([m_pv])+'%   ·   '+(IF [m_out]=0 THEN 'all in stock' ELSE STR([m_out])+' out' END)"),
    ("x_crit", "cell crit", "string", "measure", "nominal", "IF [m_status]='Critical' THEN STR([m_pv])+'%' END"),
    ("x_warn", "cell warn", "string", "measure", "nominal", "IF [m_status]='Below target' THEN STR([m_pv])+'%' END"),
    ("x_good", "cell good", "string", "measure", "nominal", "IF [m_status]='On target' THEN STR([m_pv])+'%' END"),
    ("x_frac", "cell fraction", "string", "measure", "nominal", "STR([m_in])+'/'+STR([m_sku])"),
]


def column_xml(name, caption, dt, role, typ, formula, indent="      "):
    return (f"{indent}<column caption='{a(caption)}' datatype='{dt}' name='[{name}]' role='{role}' type='{typ}'>\n"
            f"{indent}  <calculation class='tableau' formula='{a(formula)}' />\n{indent}</column>\n")


def base_columns(indent="      "):
    out = ""
    for n, dt, role, typ, agg in BASE:
        out += (f"{indent}<column aggregation='{agg}' datatype='{dt}' default-type='{typ}' layered='true' "
                f"name='[{a(n)}]' pivot='key' role='{role}' type='{typ}' user-datatype='{dt}' visual-totals='Default' />\n")
    return out


def all_columns(indent="      "):
    return base_columns(indent) + "".join(column_xml(*c, indent=indent) for c in CALCS)


def metadata_records():
    out = ""
    for i, (n, dt, role, typ, agg) in enumerate(BASE, 1):
        cls = "measure" if role == "measure" else "column"
        out += f"""          <metadata-record class='{cls}'>
            <remote-name>{escape(n)}</remote-name>
            <remote-type>{BASE_REMOTE[dt]}</remote-type>
            <local-name>[{escape(n)}]</local-name>
            <parent-name>[sqlproxy]</parent-name>
            <remote-alias>{escape(n)}</remote-alias>
            <ordinal>{i}</ordinal>
            <layered>true</layered>
            <local-type>{dt}</local-type>
            <aggregation>{agg}</aggregation>
            <contains-null>true</contains-null>
            <object-id>[_DB515E09EDDE47309FB3ED62AF3ED36F]</object-id>
          </metadata-record>
"""
    return out


def parameters_ds():
    return f"""    <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>
      <aliases enabled='yes' />
      <column caption='Target availability %' datatype='integer' name='[p_target]' param-domain-type='range' role='measure' type='quantitative' value='95'>
        <calculation class='tableau' formula='95' />
        <range granularity='1' max='100' min='50' />
      </column>
      <column caption='Critical below %' datatype='integer' name='[p_critical]' param-domain-type='range' role='measure' type='quantitative' value='80'>
        <calculation class='tableau' formula='80' />
        <range granularity='1' max='99' min='0' />
      </column>
      <column caption='Deliver within (days)' datatype='integer' name='[p_days]' param-domain-type='range' role='measure' type='quantitative' value='2'>
        <calculation class='tableau' formula='2' />
        <range granularity='1' max='14' min='0' />
      </column>
      <column caption='Qibla store' datatype='string' name='[p_qibla]' param-domain-type='list' role='measure' type='nominal' value='&quot;Exclude&quot;'>
        <calculation class='tableau' formula='&quot;Exclude&quot;' />
        <members>
          <member value='&quot;Exclude&quot;' />
          <member value='&quot;Include&quot;' />
        </members>
      </column>
    </datasource>
"""


def main_ds():
    return f"""    <datasource caption='Supplier&apos;s Availability Data' inline='true' name='{DS}' version='18.1'>
      <repository-location derived-from='https://{SERVER}/t/{SITE}/datasources/SuppliersAvailabilityData?rev=1.0' id='SuppliersAvailabilityData' path='/t/{SITE}/datasources' revision='1.0' site='{SITE}' />
      <connection channel='https' class='sqlproxy' dbname='SuppliersAvailabilityData' directory='dataserver' port='443' server='{SERVER}' server-ds-friendly-name='Supplier&apos;s Availability Data' username=''>
        <relation connection='{DS}' name='sqlproxy' table='[sqlproxy]' type='table' />
        <metadata-records>
{metadata_records()}        </metadata-records>
      </connection>
      <aliases enabled='yes' />
{all_columns()}      <column-instance column='[m_status]' derivation='User' name='[usr:m_status:nk]' pivot='key' type='nominal' />
      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />
      <style>
        <style-rule element='mark'>
          <encoding attr='color' field='[usr:m_status:nk]' type='palette'>
            <map to='{CRIT_F}'>
              <bucket>&quot;Critical&quot;</bucket>
            </map>
            <map to='{WARN_F}'>
              <bucket>&quot;Below target&quot;</bucket>
            </map>
            <map to='{GOOD_F}'>
              <bucket>&quot;On target&quot;</bucket>
            </map>
          </encoding>
        </style-rule>
      </style>
    </datasource>
"""


# --------------------------------------------------------------- worksheets
def f(col):
    return f"[{DS}].[{col}]"


def ci(inst):
    """column-instance xml for 'none:c_cat:nk' / 'usr:m_pct:qk' style names."""
    deriv, col, suffix = inst.split(":")
    typ = {"nk": "nominal", "qk": "quantitative", "ok": "ordinal"}[suffix]
    d = {"none": "None", "usr": "User"}[deriv]
    return f"            <column-instance column='[{a(col)}]' derivation='{d}' name='[{a(inst)}]' pivot='key' type='{typ}' />\n"


def run(text, color=INK, size=10, bold=False):
    b = " bold='true'" if bold else ""
    return f"                <run{b} fontcolor='{color}' fontsize='{size}'><![CDATA[{text}]]></run>\n"


def fld(inst):
    return f"<{f(inst)}>"


NL = "                <run>Æ&#10;</run>\n"


def worksheet(name, *, instances, rows="", cols="", mark="Text", text=(), label=None, color=None,
              color_map=None, extra_filters="", sorts="", styles="", size=None, show_labels=True, tooltip=None,
              align=None):
    inst_set = []
    for i in ["none:c_scope:nk", "none:c_sup:nk", *instances]:
        if i not in inst_set:
            inst_set.append(i)
    deps = all_columns("            ") + "".join(ci(i) for i in inst_set)
    enc = "".join(f"              <text column='{f(t)}' />\n" for t in text)
    if color:
        enc += f"              <color column='{f(color)}' />\n"
    if size:
        enc += f"              <size column='{f(size)}' />\n"
    lab = ""
    if label is not None:
        lab = f"""            <customized-label>
              <formatted-text>
{label}              </formatted-text>
            </customized-label>
"""
    tip = ""
    if tooltip is not None:
        tip = f"""            <customized-tooltip>
              <formatted-text>
{tooltip}              </formatted-text>
            </customized-tooltip>
"""
    cmap = ""
    if color_map:
        maps = "".join(f"            <map to='{c}'>\n              <bucket>&quot;{a(v)}&quot;</bucket>\n            </map>\n"
                       for v, c in color_map.items())
        cmap = f"""        <style-rule element='mark'>
          <encoding attr='color' field='{f(color)}' type='palette'>
{maps}          </encoding>
        </style-rule>
"""
    mark_style = ("                <format attr='mark-labels-show' value='true' />\n"
                  "                <format attr='mark-labels-cull' value='false' />\n") if show_labels else ""
    if align:
        mark_style += f"                <format attr='text-align' value='{align}' />\n"
    return f"""    <worksheet name='{a(name)}'>
      <table>
        <view>
          <datasources>
            <datasource caption='Supplier&apos;s Availability Data' name='{DS}' />
            <datasource name='Parameters' />
          </datasources>
          <datasource-dependencies datasource='{DS}'>
{deps}          </datasource-dependencies>
          <filter class='categorical' column='{f("none:c_scope:nk")}'>
            <groupfilter function='member' level='[none:c_scope:nk]' member='true' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />
          </filter>
          <filter class='categorical' column='{f("none:c_sup:nk")}' filter-group='7'>
            {sup_filter()}
          </filter>
{extra_filters}{sorts}          <slices>
            <column>{f("none:c_scope:nk")}</column>
            <column>{f("none:c_sup:nk")}</column>
{"".join(f"            <column>{f(x)}</column>" + chr(10) for x in slice_cols(extra_filters))}          </slices>
          <aggregation value='true' />
        </view>
        <style>
          <style-rule element='worksheet'>
            <format attr='display-field-labels' scope='rows' value='false' />
            <format attr='display-field-labels' scope='cols' value='false' />
          </style-rule>
{styles}{cmap}        </style>
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='{mark}' />
            <encodings>
{enc}            </encodings>
{tip}{lab}            <style>
              <style-rule element='mark'>
{mark_style}              </style-rule>
            </style>
          </pane>
        </panes>
        <rows>{rows}</rows>
        <cols>{cols}</cols>
      </table>
      <simple-id uuid='{uid()}' />
    </worksheet>
"""


def sup_filter():
    if DEFAULT_SUPPLIER:
        return (f"<groupfilter function='member' level='[none:c_sup:nk]' member='&quot;{a(DEFAULT_SUPPLIER)}&quot;' "
                "user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />")
    return "<groupfilter function='level-members' level='[none:c_sup:nk]' user:ui-enumeration='all' user:ui-marker='enumerate' />"


def slice_cols(extra):
    import re
    return re.findall(rf"column='\[{DS}\]\.\[([^\]]+)\]'", extra)


def gap_filter():
    return f"""          <filter class='categorical' column='{f("none:i_gap:nk")}'>
            <groupfilter function='member' level='[none:i_gap:nk]' member='true' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />
          </filter>
"""


def store_sort():
    buckets = "".join(f"              <bucket>&quot;{s}&quot;</bucket>\n" for s in STORES)
    return f"""          <sort class='manual' column='{f("none:Store:nk")}' direction='ASC'>
            <dictionary>
{buckets}            </dictionary>
          </sort>
"""


def bg(color):
    return f"""          <style-rule element='table'>
            <format attr='background-color' value='{color}' />
          </style-rule>
"""


STATUS_COLORS = {"Critical": CRIT_F, "Below target": WARN_F, "On target": GOOD_F}


def sheets():
    W = []
    # Header (dark band)
    W.append(worksheet(
        "R Header", instances=["usr:t_name:nk", "usr:t_meta:nk", "usr:t_date:nk"],
        text=["usr:t_name:nk", "usr:t_meta:nk", "usr:t_date:nk"], styles=bg(BAND),
        label=run("SUPPLIER AVAILABILITY REPORT", "#A9B7CD", 9, True) + NL
        + run(fld("usr:t_name:nk"), "#FFFFFF", 22, True) + NL
        + run(fld("usr:t_meta:nk"), "#D2DBE8", 10) + run("      " + fld("usr:t_date:nk"), "#A9B7CD", 9, True)))
    # Verdict
    W.append(worksheet(
        "R Verdict", instances=["usr:v_crit:nk", "usr:v_warn:nk", "usr:v_good:nk", "usr:v_text:nk"],
        text=["usr:v_crit:nk", "usr:v_warn:nk", "usr:v_good:nk", "usr:v_text:nk"],
        label=run(fld("usr:v_crit:nk"), CRIT, 16, True) + run(fld("usr:v_warn:nk"), WARN, 16, True)
        + run(fld("usr:v_good:nk"), GOOD, 16, True) + NL + run(fld("usr:v_text:nk"), INK, 12, True)))
    # Ask
    W.append(worksheet(
        "R Ask", instances=["usr:v_ask:nk"], text=["usr:v_ask:nk"], styles=bg("#F4F6FA"),
        label=run("WHAT WE NEED FROM YOU    ", INK, 9, True) + run(fld("usr:v_ask:nk"), INK, 11)))
    # Overall availability
    W.append(worksheet(
        "R Overall", instances=["usr:k_crit:nk", "usr:k_warn:nk", "usr:k_good:nk", "usr:k_gap:nk", "usr:k_shelves:nk"],
        text=["usr:k_crit:nk", "usr:k_warn:nk", "usr:k_good:nk", "usr:k_gap:nk", "usr:k_shelves:nk"],
        label=run("OVERALL AVAILABILITY", INK2, 9, True) + NL
        + run(fld("usr:k_crit:nk"), CRIT, 54, True) + run(fld("usr:k_warn:nk"), WARN, 54, True)
        + run(fld("usr:k_good:nk"), GOOD, 54, True) + NL
        + run(fld("usr:k_gap:nk"), INK, 11, True) + NL + run(fld("usr:k_shelves:nk"), INK2, 10), align="left"))
    # KPI tiles
    tiles = [
        ("R KPI Products", "YOUR PRODUCTS", "usr:m_items:qk", "listed in your stores", None),
        ("R KPI Gaps", "PRODUCTS WITH GAPS", "usr:m_gaps:qk", "out of stock in 1 or more stores", CRIT),
        ("R KPI Missing", "MISSING EVERYWHERE", "usr:m_dead:qk", "products customers can’t buy", CRIT),
        ("R KPI Empty", "EMPTY SHELVES", "usr:m_out:qk", "product-store shelves with no stock", CRIT),
    ]
    for name, lbl, meas, sub, flag in tiles:
        W.append(worksheet(
            name, instances=[meas], text=[meas],
            label=run(("■ " if flag else "") + lbl, flag or INK2, 9, True) + NL
            + run(fld(meas), INK, 26, True) + NL + run(sub, INK3, 9), align="left"))
    W.append(worksheet(
        "R KPI Top", instances=["usr:k_t1:nk", "usr:k_t1sub:nk"], text=["usr:k_t1:nk", "usr:k_t1sub:nk"],
        label=run("TOP SELLERS IN STOCK", INK2, 9, True) + NL + run(fld("usr:k_t1:nk"), INK, 26, True) + NL
        + run(fld("usr:k_t1sub:nk"), INK3, 9), align="left"))
    # Bars: stores and categories, coloured by status
    bar_style = lambda dim, width: f"""          <style-rule element='header'>
            <format attr='width' field='{f(dim)}' value='{width}' />
            <format attr='font-size' value='10' />
            <format attr='font-weight' value='bold' />
            <format attr='color' value='{INK}' />
          </style-rule>
          <style-rule element='axis'>
            <format attr='display' class='0' field='{f("usr:m_pct:qk")}' scope='cols' value='false' />
          </style-rule>
          <style-rule element='gridline'>
            <format attr='line-visibility' value='off' />
          </style-rule>
"""
    W.append(worksheet(
        "R Stores", instances=["none:Store:nk", "usr:m_pct:qk", "usr:m_status:nk", "usr:b_lbl:nk"],
        rows=f("none:Store:nk"), cols=f("usr:m_pct:qk"), mark="Bar", text=["usr:b_lbl:nk"],
        color="usr:m_status:nk", color_map=STATUS_COLORS, sorts=store_sort(), styles=bar_style("none:Store:nk", 110),
        label=run(fld("usr:b_lbl:nk"), INK, 10, True)))
    W.append(worksheet(
        "R Categories", instances=["none:c_cat:nk", "usr:m_pct:qk", "usr:m_status:nk", "usr:b_lbl:nk"],
        rows=f("none:c_cat:nk"), cols=f("usr:m_pct:qk"), mark="Bar", text=["usr:b_lbl:nk"],
        color="usr:m_status:nk", color_map=STATUS_COLORS,
        sorts=f"          <sort class='computed' column='{f('none:c_cat:nk')}' direction='ASC' using='{f('usr:m_pct:qk')}' />\n",
        styles=bar_style("none:c_cat:nk", 200), label=run(fld("usr:b_lbl:nk"), INK, 10, True)))
    # Out-of-stock lists (priority order; hidden sort key column)
    list_style = lambda cols_w: "          <style-rule element='header'>\n" + "".join(
        f"            <format attr='width' field='{f(c)}' value='{w}' />\n" for c, w in cols_w) + f"""            <format attr='font-size' value='9' />
            <format attr='color' value='{INK}' />
          </style-rule>
          <style-rule element='header'>
            <format attr='color' field='{f("none:i_key:nk")}' value='#FFFFFF' />
          </style-rule>
          <style-rule element='cell'>
            <format attr='height' value='24' />
          </style-rule>
"""
    cell_label = run(fld("none:i_out:nk"), CRIT_F, 9, True) + run(fld("none:i_ok:nk"), GOOD, 10, True)
    W.append(worksheet(
        "R Restock", instances=["none:i_key:nk", "none:Item Code:nk", "none:Item Name:nk", "none:c_type:nk",
                                "none:Store:nk", "none:i_out:nk", "none:i_ok:nk", "none:i_gap:nk"],
        rows=" / ".join(f(x) for x in ["none:i_key:nk", "none:Item Code:nk", "none:Item Name:nk", "none:c_type:nk"]),
        cols=f("none:Store:nk"), text=["none:i_out:nk", "none:i_ok:nk"], extra_filters=gap_filter(),
        sorts=store_sort(), label=cell_label,
        styles=list_style([("none:i_key:nk", 1), ("none:Item Code:nk", 70), ("none:Item Name:nk", 360),
                           ("none:c_type:nk", 90)]) + CELL_OUT_STYLE))
    W.append(worksheet(
        "D Out of stock", instances=["none:i_key:nk", "none:i_where:nk", "none:Item Code:nk", "none:Item Name:nk",
                                     "none:c_sub:nk", "none:c_type:nk", "none:Store:nk", "none:i_out:nk",
                                     "none:i_ok:nk", "none:i_gap:nk"],
        rows=" / ".join(f(x) for x in ["none:i_where:nk", "none:i_key:nk", "none:Item Code:nk", "none:Item Name:nk",
                                        "none:c_sub:nk", "none:c_type:nk"]),
        cols=f("none:Store:nk"), text=["none:i_out:nk", "none:i_ok:nk"], extra_filters=gap_filter(),
        sorts=store_sort(), label=cell_label,
        styles=list_style([("none:i_where:nk", 120), ("none:i_key:nk", 1), ("none:Item Code:nk", 70),
                           ("none:Item Name:nk", 320), ("none:c_sub:nk", 130), ("none:c_type:nk", 90)]) + CELL_OUT_STYLE))
    # Category x store grid
    grid_label = (run(fld("usr:x_crit:nk"), CRIT, 12, True) + run(fld("usr:x_warn:nk"), WARN, 12, True)
                  + run(fld("usr:x_good:nk"), GOOD, 12, True) + run("   " + fld("usr:x_frac:nk"), INK3, 9))
    grid_inst = ["usr:x_crit:nk", "usr:x_warn:nk", "usr:x_good:nk", "usr:x_frac:nk"]
    grid_style = lambda extra="": f"""          <style-rule element='header'>
            <format attr='width' field='{f("none:c_cat:nk")}' value='170' />
            <format attr='width' field='{f("none:c_sub:nk")}' value='170' />
            <format attr='font-size' value='10' />
            <format attr='color' value='{INK}' />
          </style-rule>
          <style-rule element='cell'>
            <format attr='height' value='26' />
            <format attr='width' value='118' />
          </style-rule>
{extra}"""
    W.append(worksheet(
        "D Grid", instances=["none:c_cat:nk", "none:c_sub:nk", "none:Store:nk", *grid_inst],
        rows=f"{f('none:c_cat:nk')} / {f('none:c_sub:nk')}", cols=f("none:Store:nk"), text=grid_inst,
        sorts=store_sort(), label=grid_label, styles=grid_style()))
    W.append(worksheet(
        "D Grid Stores", instances=["none:Store:nk", *grid_inst], cols=f("none:Store:nk"), text=grid_inst,
        sorts=store_sort(), label=grid_label, styles=grid_style()))
    W.append(worksheet("D Grid All", instances=grid_inst, text=grid_inst, label=grid_label))
    return W


# Store cells of the out-of-stock lists: red fill behind "OUT" is drawn by the label
# colour on a red mark background, which Tableau cannot do per value, so OUT is
# bold red text on white and in-stock cells show a green tick.
CELL_OUT_STYLE = ""


# --------------------------------------------------------------- dashboards
def zone_sheet(zid, name, x, y, w, h, bgc="#FFFFFF", border=False, margin=4):
    b = (f"""              <format attr='border-color' value='#E2E7EF' />
              <format attr='border-style' value='solid' />
              <format attr='border-width' value='1' />
""" if border else "")
    return f"""          <zone h='{h}' id='{zid}' name='{a(name)}' show-title='false' w='{w}' x='{x}' y='{y}'>
            <zone-style>
              <format attr='background-color' value='{bgc}' />
{b}              <format attr='margin' value='{margin}' />
            </zone-style>
          </zone>
"""


def zone_text(zid, x, y, w, h, runs):
    return f"""          <zone h='{h}' id='{zid}' type-v2='text' w='{w}' x='{x}' y='{y}'>
            <formatted-text>
{runs}            </formatted-text>
          </zone>
"""


def dashboard(name, width, height, zones):
    return f"""    <dashboard name='{a(name)}'>
      <style />
      <size maxheight='{height}' maxwidth='{width}' minheight='{height}' minwidth='{width}' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
{zones}          <zone-style>
            <format attr='background-color' value='#FFFFFF' />
          </zone-style>
        </zone>
      </zones>
      <simple-id uuid='{uid()}' />
    </dashboard>
"""


def px(v, total):
    return int(round(v / total * 100000))


def report_dashboard():
    W, H = 1080, 1620
    X = lambda v: px(v, W)
    Y = lambda v: px(v, H)
    z, i = "", 10
    def S(name, x, y, w, h, **k):
        nonlocal z, i
        i += 1
        z += zone_sheet(i, name, X(x), Y(y), X(w), Y(h), **k)
    def T(x, y, w, h, runs):
        nonlocal z, i
        i += 1
        z += zone_text(i, X(x), Y(y), X(w), Y(h), runs)
    # control strip
    i += 1
    z += (f"          <zone h='{Y(36)}' id='{i}' mode='typeinlist' name='R Header' param='{f('none:c_sup:nk')}' "
          f"type-v2='filter' values='database' w='{X(560)}' x='{X(16)}' y='{Y(2)}' />\n")
    S("R Header", 0, 40, 1080, 130, bgc=BAND, margin=14)
    S("R Verdict", 0, 170, 1080, 88, bgc="#FFFFFF", margin=12)
    S("R Ask", 0, 258, 1080, 46, bgc="#F4F6FA", margin=8)
    S("R Overall", 24, 318, 330, 200, margin=8)
    S("R KPI Products", 370, 316, 225, 104, border=True, margin=6)
    S("R KPI Gaps", 600, 316, 225, 104, border=True, margin=6)
    S("R KPI Missing", 830, 316, 226, 104, border=True, margin=6)
    S("R KPI Empty", 370, 424, 225, 104, border=True, margin=6)
    S("R KPI Top", 600, 424, 225, 104, border=True, margin=6)
    T(830, 432, 226, 80, run("Colours", INK2, 9, True) + NL + run("■ On target (95%+)", GOOD_F, 9, True) + NL
      + run("■ Below target (80–94%)", WARN_F, 9, True) + NL + run("■ Critical (under 80%)", CRIT_F, 9, True))
    T(24, 536, 1032, 30, run("Availability by store", INK, 15, True) + run("     share of your shelves with stock", INK3, 9))
    S("R Stores", 24, 566, 1032, 170)
    T(24, 748, 1032, 30, run("Where you are losing", INK, 15, True) + run("     categories, weakest first", INK3, 9))
    S("R Categories", 24, 778, 1032, 300)
    T(24, 1090, 1032, 30, run("Restock these first", INK, 15, True)
      + run("     top sellers first · OUT = out of stock in that store · full list on the Detail page", INK3, 9))
    S("R Restock", 24, 1120, 1032, 430)
    T(24, 1560, 1032, 52, run(
        "How to read this: each of your products in each store is one shelf. Availability = shelves with stock ÷ all "
        "your shelves. A shelf counts as in stock when the store has at least one unit. Products marked inactive or "
        "on hold in our item master are not counted.", INK3, 8))
    return dashboard("Supplier Report", W, H, z)


def detail_dashboard():
    W, H = 1080, 1620
    X = lambda v: px(v, W)
    Y = lambda v: px(v, H)
    z, i = "", 100
    def S(name, x, y, w, h, **k):
        nonlocal z, i
        i += 1
        z += zone_sheet(i, name, X(x), Y(y), X(w), Y(h), **k)
    def T(x, y, w, h, runs):
        nonlocal z, i
        i += 1
        z += zone_text(i, X(x), Y(y), X(w), Y(h), runs)
    S("R Header", 0, 0, 1080, 120, bgc=BAND, margin=14)
    T(24, 132, 1032, 30, run("Availability by category and store", INK, 15, True)
      + run("     % in stock, then shelves stocked / total · bottom row: all categories", INK3, 9))
    S("D Grid", 24, 162, 1032, 560)
    S("D Grid Stores", 24, 722, 900, 50, bgc="#F4F6FA")
    S("D Grid All", 924, 722, 132, 50, bgc="#E9EDF3")
    T(24, 776, 1032, 30, run("Out-of-stock action list", INK, 15, True)
      + run("     every product that is out somewhere · most urgent first", INK3, 9))
    S("D Out of stock", 24, 806, 1032, 790)
    return dashboard("Detail", W, H, z)


def windows(sheet_names):
    def vps(names):
        wide = {"R Restock", "D Out of stock"}
        return "".join(f"        <viewpoint name='{a(n)}'>\n          <zoom type='{'fit-width' if n in wide else 'entire-view'}' />\n        </viewpoint>\n"
                       for n in names)
    rep = [n for n in sheet_names if n.startswith("R ")]
    det = ["R Header"] + [n for n in sheet_names if n.startswith("D ")]
    out = f"""  <windows source-height='51'>
    <window class='dashboard' maximized='true' name='Supplier Report'>
      <viewpoints>
{vps(rep)}      </viewpoints>
      <active id='11' />
      <simple-id uuid='{uid()}' />
    </window>
    <window class='dashboard' maximized='true' name='Detail'>
      <viewpoints>
{vps(det)}      </viewpoints>
      <active id='11' />
      <simple-id uuid='{uid()}' />
    </window>
"""
    for n in sheet_names:
        out += f"""    <window class='worksheet' hidden='true' name='{a(n)}'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='31'>
            <card type='columns' />
          </strip>
          <strip size='31'>
            <card type='rows' />
          </strip>
        </edge>
      </cards>
      <simple-id uuid='{uid()}' />
    </window>
"""
    return out + "  </windows>\n"


def build():
    import re
    ws = sheets()
    names = re.findall(r"<worksheet name='([^']+)'", "".join(ws))
    names = [n.replace("&apos;", "'") for n in names]
    return f"""<?xml version='1.0' encoding='utf-8' ?>

<workbook locale='en_US' original-version='18.1' source-build='2026.2.6 (20262.26.0915.0020)' version='18.1' xml:base='https://{SERVER}' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <AnimationOnByDefault />
    <ISO8601DefaultCalendarPref />
    <MarkAnimation />
    <ObjectModelEncapsulateLegacy />
    <ObjectModelTableType />
    <SchemaViewerObjectModel />
    <SheetIdentifierTracking />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences />
  <datasources>
{parameters_ds()}{main_ds()}  </datasources>
  <worksheets>
{"".join(ws)}  </worksheets>
  <dashboards>
{report_dashboard()}{detail_dashboard()}  </dashboards>
{windows(names)}</workbook>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    import xml.dom.minidom
    xml.dom.minidom.parse(str(OUT))  # well-formed check
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
