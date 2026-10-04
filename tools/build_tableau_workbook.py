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
    ("i_rank", "Priority score", "integer", "measure", "quantitative",
     # Same order as i_key, as a number for the top-15 filter on page 1.
     "IF [i_gap] THEN (IF [Rank]='T1' OR [Rank]='T2' THEN 100000 ELSE 0 END)"
     "+(IF [i_in]=0 THEN 10000 ELSE 0 END)"
     "+100*(CASE [Rank] WHEN 'T1' THEN 9 WHEN 'T2' THEN 8 WHEN 'T3' THEN 7 WHEN 'T4' THEN 6 "
     "WHEN 'T5' THEN 5 WHEN 'TN' THEN 4 ELSE 3 END)+([i_sku]-[i_in]) ELSE -1 END"),
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
    ("x_frac", "cell fraction", "string", "measure", "nominal", "STR([m_in])+' / '+STR([m_sku])"),
    ("i_state", "Cell state", "string", "dimension", "nominal", "IF [Items in Stock]='Yes' THEN 'In' ELSE 'Out' END"),
    ("b_one", "Full bar", "real", "measure", "quantitative", "IF [m_sku]>=0 THEN 1.0 END"),
    ("s_strong", "Status band", "string", "measure", "nominal", "[m_status]"),
    ("s_tint", "Status tint", "string", "measure", "nominal", "[m_status]"),
    ("v_txt_w", "Verdict light", "string", "measure", "nominal", "IF [m_status]<>'Below target' THEN [v_text] END"),
    ("v_txt_k", "Verdict dark", "string", "measure", "nominal", "IF [m_status]='Below target' THEN [v_text] END"),
    ("sc_sub", "Store line", "string", "measure", "nominal",
     "IF [m_out]=0 THEN 'all '+STR([m_in])+' in stock' ELSE STR([m_out])+' out of stock  ·  '+STR([m_in])+' in stock' END"),
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
      <column caption='Target availability %' datatype='integer' name='[p_target]' param-domain-type='range' role='measure' type='quantitative' value='85'>
        <calculation class='tableau' formula='85' />
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


BAND_PAL = """          <encoding attr='color' field='[usr:s_strong:nk]' type='palette'>
            <map to='#B42318'>
              <bucket>&quot;Critical&quot;</bucket>
            </map>
            <map to='#F5A524'>
              <bucket>&quot;Below target&quot;</bucket>
            </map>
            <map to='#0E6B3B'>
              <bucket>&quot;On target&quot;</bucket>
            </map>
          </encoding>
"""
TINT_PAL = """          <encoding attr='color' field='[usr:s_tint:nk]' type='palette'>
            <map to='#FDE4E1'>
              <bucket>&quot;Critical&quot;</bucket>
            </map>
            <map to='#FEF1D6'>
              <bucket>&quot;Below target&quot;</bucket>
            </map>
            <map to='#DDF3E5'>
              <bucket>&quot;On target&quot;</bucket>
            </map>
          </encoding>
"""


STATE_PAL = """          <encoding attr='color' field='[none:i_state:nk]' type='palette'>
            <map to='#D92D20'>
              <bucket>&quot;Out&quot;</bucket>
            </map>
            <map to='#FFFFFF'>
              <bucket>&quot;In&quot;</bucket>
            </map>
          </encoding>
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
      <column-instance column='[s_strong]' derivation='User' name='[usr:s_strong:nk]' pivot='key' type='nominal' />
      <column-instance column='[s_tint]' derivation='User' name='[usr:s_tint:nk]' pivot='key' type='nominal' />
      <column-instance column='[i_state]' derivation='None' name='[none:i_state:nk]' pivot='key' type='nominal' />
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
{BAND_PAL}{TINT_PAL}{STATE_PAL}        </style-rule>
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


def run(text, color=INK, size=10, bold=False, font=None):
    font = font or ("Tableau Bold" if bold else "Tableau Book")
    b = " bold='true'" if bold and font == "Tableau Bold" else ""
    return (f"                <run{b} fontcolor='{color}' fontname='{font}' fontsize='{size}'>"
            f"<![CDATA[{text}]]></run>\n")


def semi(text, color=INK, size=10):
    return run(text, color, size, font="Tableau Semibold")


def fld(inst):
    return f"<{f(inst)}>"


NL = "                <run>Æ&#10;</run>\n"


def worksheet(name, *, instances, rows="", cols="", mark="Text", text=(), label=None, color=None,
              color_map=None, extra_filters="", sorts="", styles="", size=None, show_labels=True, tooltip=None,
              align=None, mark_extra="", cell=None, instances_extra=(), hide_head=False):
    if hide_head:
        styles += """          <style-rule element='header'>
            <format attr='color' value='#FFFFFF' />
          </style-rule>
"""
    instances = [*instances, *instances_extra]
    if cell:
        styles += f"""          <style-rule element='cell'>
            <format attr='width' value='{cell[0]}' />
            <format attr='height' value='{cell[1]}' />
          </style-rule>
"""
    if mark == "Square" and "attr='size'" not in mark_extra:
        mark_extra += "                <format attr='size' value='1' />\n"
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
    mark_style += mark_extra
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
          <filter class='categorical' column='{f("none:c_sup:nk")}' filter-group='7' context='true'>
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


def top_restock(n=15):
    return gap_filter() + f"""          <filter class='categorical' column='{f("none:i_key:nk")}'>
            <groupfilter count='{n}' end='top' function='end' units='records' user:ui-marker='end' user:ui-top-by-field='true'>
              <groupfilter direction='DESC' expression='MAX([i_rank])' function='order' user:ui-marker='order'>
                <groupfilter function='level-members' level='[none:i_key:nk]' user:ui-enumeration='all' user:ui-marker='enumerate' />
              </groupfilter>
            </groupfilter>
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
WASH = "#F4F6FA"
HEAD_FONT = """          <style-rule element='header'>
            <format attr='font-family' value='Tableau Semibold' />
            <format attr='font-size' value='10' />
            <format attr='color' value='#46536B' />
          </style-rule>
"""
NO_LINES = """          <style-rule element='gridline'>
            <format attr='line-visibility' value='off' />
          </style-rule>
          <style-rule element='zeroline'>
            <format attr='line-visibility' value='off' />
          </style-rule>
          <style-rule element='table-div'>
            <format attr='line-visibility' scope='rows' value='off' />
            <format attr='line-visibility' scope='cols' value='off' />
          </style-rule>
"""


CLEAR = """          <style-rule element='table'>
            <format attr='background-color' value='#00000000' />
          </style-rule>
          <style-rule element='worksheet'>
            <format attr='background-color' value='#00000000' />
          </style-rule>
          <style-rule element='pane'>
            <format attr='background-color' value='#00000000' />
          </style-rule>
"""
ONE = "usr:b_one:qk"


def fixed_axis(inst, top=1):
    return f"""          <style-rule element='axis'>
            <encoding attr='space' class='0' field='{f(inst)}' field-type='quantitative' max='{top}' min='0' range-type='fixed' scope='cols' type='space' />
            <format attr='display' class='0' field='{f(inst)}' scope='cols' value='false' />
          </style-rule>
"""


def size(v):
    return f"                <format attr='size' value='{v}' />\n"


def status_runs(prefix, size):
    return (run(fld(f"usr:{prefix}_crit:nk"), CRIT, size, True) + run(fld(f"usr:{prefix}_warn:nk"), WARN, size, True)
            + run(fld(f"usr:{prefix}_good:nk"), GOOD, size, True))


def sheets():
    W = []
    # Header band
    W.append(worksheet(
        "R Header", instances=["usr:t_name:nk", "usr:t_meta:nk", "usr:t_date:nk"],
        text=["usr:t_name:nk", "usr:t_meta:nk", "usr:t_date:nk"], styles=bg(BAND), align="left", cell=(1030, 100),
        label=semi("SUPPLIER AVAILABILITY REPORT", "#A9B7CD", 9) + NL
        + run(fld("usr:t_name:nk"), "#FFFFFF", 24, True) + NL
        + run(fld("usr:t_meta:nk"), "#D2DBE8", 10) + semi("        " + fld("usr:t_date:nk"), "#A9B7CD", 9)))
    # Verdict: a solid status-coloured band (single-cell highlight table)
    W.append(worksheet(
        "R Verdict", instances=["usr:v_crit:nk", "usr:v_warn:nk", "usr:v_good:nk", "usr:v_txt_w:nk",
                                "usr:v_txt_k:nk", "usr:s_strong:nk"],
        text=[],
        instances_extra=["usr:b_one:qk"], cols=f("usr:b_one:qk"),
        mark="Bar", color="usr:s_strong:nk", align="left", styles=NO_LINES + f"""          <style-rule element='axis'>
            <encoding attr='space' class='0' field='{f("usr:b_one:qk")}' field-type='quantitative' max='1' min='0' range-type='fixed' scope='cols' type='space' />
            <format attr='display' class='0' field='{f("usr:b_one:qk")}' scope='cols' value='false' />
          </style-rule>
""",
        mark_extra="                <format attr='size' value='3' />\n", show_labels=False, label=None))
    # Verdict text, transparent, laid over the band
    W.append(worksheet(
        "R Verdict Text", instances=["usr:v_crit:nk", "usr:v_warn:nk", "usr:v_good:nk", "usr:v_txt_w:nk",
                                     "usr:v_txt_k:nk"],
        text=["usr:v_crit:nk", "usr:v_warn:nk", "usr:v_good:nk", "usr:v_txt_w:nk", "usr:v_txt_k:nk"],
        align="left", styles=CLEAR,
        label=run(fld("usr:v_crit:nk"), "#FFFFFF", 17, True) + run(fld("usr:v_warn:nk"), INK, 17, True)
        + run(fld("usr:v_good:nk"), "#FFFFFF", 17, True) + NL
        + semi(fld("usr:v_txt_w:nk"), "#FFFFFF", 12) + semi(fld("usr:v_txt_k:nk"), INK, 12)))
    W.append(worksheet(
        "R Ask", instances=["usr:v_ask:nk"], text=["usr:v_ask:nk"], styles=bg(WASH), align="left", cell=(1060, 40),
        label=run("WHAT WE NEED FROM YOU     ", INK, 9, True) + run(fld("usr:v_ask:nk"), INK, 11)))
    # Overall availability card, tinted by status
    W.append(worksheet(
        "R Overall BG", instances=["usr:s_tint:nk"], instances_extra=[ONE], cols=f(ONE), mark="Bar",
        color="usr:s_tint:nk", styles=NO_LINES + fixed_axis(ONE), mark_extra=size(3), show_labels=False))
    W.append(worksheet(
        "R Overall", instances=["usr:k_crit:nk", "usr:k_warn:nk", "usr:k_good:nk", "usr:k_gap:nk",
                                "usr:k_shelves:nk", "usr:s_tint:nk"],
        text=["usr:k_crit:nk", "usr:k_warn:nk", "usr:k_good:nk", "usr:k_gap:nk", "usr:k_shelves:nk"],
        align="left", styles=CLEAR,
        label=semi("OVERALL AVAILABILITY", INK2, 9) + NL + status_runs("k", 58) + NL
        + semi(fld("usr:k_gap:nk"), INK, 11) + NL + run(fld("usr:k_shelves:nk"), INK2, 10)))
    # KPI tiles on a soft wash
    tiles = [
        ("R KPI Products", "YOUR PRODUCTS", "usr:m_items:qk", "listed in your stores", None),
        ("R KPI Gaps", "PRODUCTS WITH GAPS", "usr:m_gaps:qk", "out of stock in 1+ stores", CRIT),
        ("R KPI Missing", "MISSING EVERYWHERE", "usr:m_dead:qk", "customers can’t buy these", CRIT),
        ("R KPI Empty", "EMPTY SHELVES", "usr:m_out:qk", "product-store shelves", CRIT),
    ]
    for name, lbl, meas, sub, flag in tiles:
        W.append(worksheet(
            name, instances=[meas], text=[meas], styles=bg(WASH), align="left", cell=(200, 92),
            label=semi(("● " if flag else "") + lbl, flag or INK2, 9) + NL
            + run(fld(meas), INK, 24, True) + NL + run(sub, INK3, 9)))
    W.append(worksheet(
        "R KPI Top", instances=["usr:k_t1:nk", "usr:k_t1sub:nk"], text=["usr:k_t1:nk", "usr:k_t1sub:nk"],
        styles=bg(WASH), align="left", cell=(200, 92),
        label=semi("TOP SELLERS IN STOCK", INK2, 9) + NL + run(fld("usr:k_t1:nk"), INK, 24, True) + NL
        + run(fld("usr:k_t1sub:nk"), INK3, 9)))
    # Store cards: one tinted cell per store
    W.append(worksheet(
        "R Stores BG", instances=["none:Store:nk", "usr:s_tint:nk"], instances_extra=[ONE],
        cols=f"{f('none:Store:nk')} / {f(ONE)}", mark="Bar", color="usr:s_tint:nk", sorts=store_sort(),
        styles=HEAD_FONT + NO_LINES + f"""          <style-rule element='header'>
            <format attr='height' field='{f("none:Store:nk")}' value='30' />
            <format attr='font-size' value='11' />
            <format attr='color' value='{INK}' />
          </style-rule>
""" + fixed_axis(ONE, 1.035), mark_extra=size(3), show_labels=False))
    W.append(worksheet(
        "R Stores", instances=["none:Store:nk", "usr:x_crit:nk", "usr:x_warn:nk", "usr:x_good:nk",
                               "usr:sc_sub:nk", "usr:s_tint:nk"],
        cols=f("none:Store:nk"), text=["usr:x_crit:nk", "usr:x_warn:nk", "usr:x_good:nk", "usr:sc_sub:nk"],
        sorts=store_sort(), align="left",
        styles=CLEAR + HEAD_FONT + NO_LINES + f"""          <style-rule element='header'>
            <format attr='height' field='{f("none:Store:nk")}' value='30' />
            <format attr='font-size' value='11' />
            <format attr='color' field='{f("none:Store:nk")}' value='#FFFFFF' />
          </style-rule>
""",
        label=status_runs("x", 34) + NL + run(fld("usr:sc_sub:nk"), INK2, 10)))
    # Category bars coloured by status
    cat_sort = f"          <sort class='computed' column='{f('none:c_cat:nk')}' direction='ASC' using='{f('usr:m_pct:qk')}' />\n"
    W.append(worksheet(
        "R Categories BG", instances=["none:c_cat:nk", "usr:m_pct:qk"], instances_extra=[ONE],
        rows=f("none:c_cat:nk"), cols=f(ONE), mark="Bar", sorts=cat_sort,
        styles=HEAD_FONT + NO_LINES + f"""          <style-rule element='header'>
            <format attr='width' field='{f("none:c_cat:nk")}' value='190' />
            <format attr='color' value='{INK}' />
          </style-rule>
""" + fixed_axis(ONE, 1.2), show_labels=False,
        mark_extra=size(0.45) + "                <format attr='mark-color' value='#EDF0F5' />\n"))
    W.append(worksheet(
        "R Categories", instances=["none:c_cat:nk", "usr:m_pct:qk", "usr:m_status:nk", "usr:b_lbl:nk"],
        rows=f("none:c_cat:nk"), cols=f("usr:m_pct:qk"), mark="Bar", text=["usr:b_lbl:nk"],
        color="usr:m_status:nk",
        sorts=f"          <sort class='computed' column='{f('none:c_cat:nk')}' direction='ASC' using='{f('usr:m_pct:qk')}' />\n",
        styles=CLEAR + HEAD_FONT + NO_LINES + f"""          <style-rule element='header'>
            <format attr='width' field='{f("none:c_cat:nk")}' value='190' />
            <format attr='color' value='{INK}' />
          </style-rule>
""" + fixed_axis("usr:m_pct:qk", 1.2),
        mark_extra="                <format attr='size' value='0.45' />\n",
        label=semi(fld("usr:b_lbl:nk"), INK, 10)))
    # Out-of-stock lists
    def list_style(cols_w):
        return HEAD_FONT + "          <style-rule element='header'>\n" + "".join(
            f"            <format attr='width' field='{f(c)}' value='{w}' />\n" for c, w in cols_w) + f"""            <format attr='color' value='{INK}' />
            <format attr='font-family' value='Tableau Book' />
          </style-rule>
          <style-rule element='header'>
            <format attr='color' field='{f("none:i_key:nk")}' value='#FFFFFF' />
          </style-rule>
          <style-rule element='cell'>
            <format attr='height' value='26' />
          </style-rule>
          <style-rule element='table-div'>
            <format attr='line-visibility' scope='cols' value='off' />
          </style-rule>
""" + fixed_axis(ONE, 1.12) + NO_LINES.split("          <style-rule element='table-div'>")[0]
    cell_label = semi(fld("none:i_out:nk"), "#FFFFFF", 9) + run(fld("none:i_ok:nk"), GOOD, 11, True)
    W.append(worksheet(
        "R Restock", instances=["none:i_key:nk", "none:Item Code:nk", "none:Item Name:nk", "none:c_type:nk",
                                "none:Store:nk", "none:i_out:nk", "none:i_ok:nk", "none:i_gap:nk"],
        rows=" / ".join(f(x) for x in ["none:i_key:nk", "none:Item Code:nk", "none:Item Name:nk", "none:c_type:nk"]),
        cols=f"{f('none:Store:nk')} / {f(ONE)}", text=["none:i_out:nk", "none:i_ok:nk"], extra_filters=top_restock(),
        sorts=store_sort(), label=cell_label, mark="Bar", color="none:i_state:nk", instances_extra=[ONE, "none:i_state:nk"],
        mark_extra=size(1.7),
        styles=list_style([("none:i_key:nk", 1), ("none:Item Code:nk", 74), ("none:Item Name:nk", 380),
                           ("none:c_type:nk", 96)])))
    W.append(worksheet(
        "D Out of stock", instances=["none:i_key:nk", "none:i_where:nk", "none:Item Code:nk", "none:Item Name:nk",
                                     "none:c_sub:nk", "none:c_type:nk", "none:Store:nk", "none:i_out:nk",
                                     "none:i_ok:nk", "none:i_gap:nk"],
        rows=" / ".join(f(x) for x in ["none:i_where:nk", "none:i_key:nk", "none:Item Code:nk", "none:Item Name:nk",
                                        "none:c_sub:nk", "none:c_type:nk"]),
        cols=f"{f('none:Store:nk')} / {f(ONE)}", text=["none:i_out:nk", "none:i_ok:nk"], extra_filters=gap_filter(),
        sorts=store_sort(), label=cell_label, mark="Bar", color="none:i_state:nk", instances_extra=[ONE, "none:i_state:nk"],
        mark_extra=size(1.7),
        styles=list_style([("none:i_where:nk", 120), ("none:i_key:nk", 1), ("none:Item Code:nk", 70),
                           ("none:Item Name:nk", 320), ("none:c_sub:nk", 130), ("none:c_type:nk", 90)])))
    # Category x store grid as a tinted highlight table
    grid_label = status_runs("x", 12) + run("   " + fld("usr:x_frac:nk"), INK3, 9)
    grid_inst = ["usr:x_crit:nk", "usr:x_warn:nk", "usr:x_good:nk", "usr:x_frac:nk", "usr:s_tint:nk"]
    grid_text = ["usr:x_crit:nk", "usr:x_warn:nk", "usr:x_good:nk", "usr:x_frac:nk"]
    grid_style = HEAD_FONT + f"""          <style-rule element='header'>
            <format attr='width' field='{f("none:c_cat:nk")}' value='170' />
            <format attr='width' field='{f("none:c_sub:nk")}' value='190' />
            <format attr='color' value='{INK}' />
          </style-rule>
          <style-rule element='table-div'>
            <format attr='line-visibility' scope='cols' value='off' />
          </style-rule>
"""
    # Overlays keep their headers for alignment but paint them white; the BG sheet shows them.
    ghost = f"""          <style-rule element='header'>
            <format attr='color' field='{f("none:Store:nk")}' value='#FFFFFF' />
          </style-rule>
"""
    bgk = dict(mark="Bar", color="usr:s_tint:nk", mark_extra=size(3), show_labels=False, instances_extra=[ONE])
    W.append(worksheet(
        "D Grid BG", instances=["none:c_cat:nk", "none:c_sub:nk", "none:Store:nk", "usr:s_tint:nk"],
        rows=f"{f('none:c_cat:nk')} / {f('none:c_sub:nk')}", cols=f"{f('none:Store:nk')} / {f(ONE)}",
        sorts=store_sort(), styles=grid_style + fixed_axis(ONE), **bgk))
    W.append(worksheet(
        "D Grid", instances=["none:c_cat:nk", "none:c_sub:nk", "none:Store:nk", *grid_inst],
        rows=f"{f('none:c_cat:nk')} / {f('none:c_sub:nk')}", cols=f("none:Store:nk"), text=grid_text,
        sorts=store_sort(), label=grid_label, styles=CLEAR + grid_style + ghost))
    W.append(worksheet(
        "D Grid Stores BG", instances=["none:Store:nk", "usr:s_tint:nk"], cols=f"{f('none:Store:nk')} / {f(ONE)}",
        sorts=store_sort(), styles=grid_style + fixed_axis(ONE), **bgk))
    W.append(worksheet(
        "D Grid Stores", instances=["none:Store:nk", *grid_inst], cols=f("none:Store:nk"), text=grid_text,
        sorts=store_sort(), label=grid_label, styles=CLEAR + grid_style + ghost))
    return W


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


def zone_text(zid, x, y, w, h, runs, bgc=None):
    st = f"""            <zone-style>
              <format attr='background-color' value='{bgc}' />
            </zone-style>
""" if bgc else ""
    return f"""          <zone h='{h}' id='{zid}' type-v2='text' w='{w}' x='{x}' y='{y}'>
            <formatted-text>
{runs}            </formatted-text>
{st}          </zone>
"""


def zone_blank(zid, x, y, w, h, bgc):
    return f"""          <zone h='{h}' id='{zid}' type-v2='empty' w='{w}' x='{x}' y='{y}'>
            <zone-style>
              <format attr='background-color' value='{bgc}' />
            </zone-style>
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


class Layout:
    def __init__(self, w, h, start_id):
        self.W, self.H, self.i, self.z = w, h, start_id, ""

    def _box(self, x, y, w, h):
        return px(x, self.W), px(y, self.H), px(w, self.W), px(h, self.H)

    def sheet(self, name, x, y, w, h, **k):
        self.i += 1
        self.z += zone_sheet(self.i, name, *self._box(x, y, w, h), **k)

    def text(self, x, y, w, h, runs, bgc=None):
        self.i += 1
        self.z += zone_text(self.i, *self._box(x, y, w, h), runs, bgc)

    def blank(self, x, y, w, h, bgc):
        self.i += 1
        self.z += zone_blank(self.i, *self._box(x, y, w, h), bgc)

    def filter(self, sheet, x, y, w, h):
        self.i += 1
        X, Y, Wd, Hd = self._box(x, y, w, h)
        self.z += (f"          <zone h='{Hd}' id='{self.i}' mode='dropdown' name='{a(sheet)}' param='{f('none:c_sup:nk')}' "
                   f"type-v2='filter' values='database' w='{Wd}' x='{X}' y='{Y}' />\n")


def section_title(L, y, title, note):
    L.text(40, y, 1000, 34, run(title, INK, 16, True) + run("      " + note, INK3, 9))


def report_dashboard():
    L = Layout(1080, 1640, 10)
    L.blank(0, 0, 1080, 52, WASH)
    L.filter("R Header", 40, 8, 520, 38)
    L.text(600, 12, 440, 30, run("Pick a supplier, then Download → Image to send", INK3, 9), WASH)
    L.sheet("R Header", 0, 52, 1080, 130, bgc=BAND, margin=22)
    L.sheet("R Verdict", 0, 182, 1080, 86, bgc="#FFFFFF", margin=0)
    L.sheet("R Verdict Text", 30, 188, 1030, 74, bgc="#00000000", margin=0)
    L.sheet("R Ask", 0, 268, 1080, 48, bgc=WASH, margin=10)
    L.sheet("R Overall BG", 40, 336, 320, 212, margin=0)
    L.sheet("R Overall", 52, 346, 300, 194, bgc="#00000000", margin=0)
    for idx, name in enumerate(["R KPI Products", "R KPI Gaps", "R KPI Missing"]):
        L.sheet(name, 380 + idx * 222, 336, 210, 102, bgc=WASH, margin=4)
    for idx, name in enumerate(["R KPI Empty", "R KPI Top"]):
        L.sheet(name, 380 + idx * 222, 446, 210, 102, bgc=WASH, margin=4)
    L.text(824, 446, 216, 102, semi("HOW TO READ THE COLOURS", INK2, 8) + NL
           + run("■ ", GOOD_F, 11) + run("On target  85%+", INK, 9) + NL
           + run("■ ", WARN_F, 11) + run("Below target  80–84%", INK, 9) + NL
           + run("■ ", CRIT_F, 11) + run("Critical  under 80%", INK, 9))
    section_title(L, 566, "Availability by store", "share of your shelves with stock")
    L.sheet("R Stores BG", 40, 600, 1000, 132, margin=0)
    L.sheet("R Stores", 40, 600, 1000, 132, bgc="#00000000", margin=0)
    section_title(L, 750, "Where you are losing", "your categories, weakest first")
    L.sheet("R Categories BG", 40, 784, 1000, 280, margin=0)
    L.sheet("R Categories", 40, 784, 1000, 280, bgc="#00000000", margin=0)
    section_title(L, 1080, "Restock these first", "15 most urgent, top sellers first  ·  OUT = out of stock in that store  ·  full list on the Detail page")
    L.sheet("R Restock", 40, 1114, 1000, 460, margin=0)
    L.text(40, 1584, 1000, 50, run(
        "How to read this: each of your products in each store is one shelf. Availability = shelves with stock ÷ all "
        "your shelves. A shelf counts as in stock when the store has at least one unit. Products marked inactive or "
        "on hold in our item master are not counted.", INK3, 8))
    return dashboard("Supplier Report", L.W, L.H, L.z)


def detail_dashboard():
    L = Layout(1080, 1640, 100)
    L.sheet("R Header", 0, 0, 1080, 130, bgc=BAND, margin=22)
    section_title(L, 148, "Availability by category and store", "% in stock, then shelves stocked / total")
    L.sheet("D Grid BG", 40, 184, 1000, 560, margin=0)
    L.sheet("D Grid", 40, 184, 1000, 560, bgc="#00000000", margin=0)
    # The store-total row sits under the store columns (row headers are 360 px wide).
    L.text(40, 772, 362, 30, run("All categories", INK, 10, True))
    L.sheet("D Grid Stores BG", 402, 748, 638, 56, margin=0)
    L.sheet("D Grid Stores", 402, 748, 638, 56, bgc="#00000000", margin=0)
    section_title(L, 818, "Out-of-stock action list", "every product that is out somewhere  ·  most urgent first")
    L.sheet("D Out of stock", 40, 852, 1000, 770, margin=0)
    return dashboard("Detail", L.W, L.H, L.z)


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
