"""Self-contained HTML report writer using Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, select_autoescape

from insecure_tree.models import Report, ScanStatus

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>insecure-tree report</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2em; color: #222; }
  h1 { color: #b91c1c; }
  h2 { color: #374151; border-bottom: 1px solid #d1d5db; padding-bottom: 4px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }
  th { background: #f3f4f6; text-align: left; padding: 8px; border: 1px solid #d1d5db; cursor: pointer; user-select: none; }
  td { padding: 6px 8px; border: 1px solid #e5e7eb; vertical-align: top; }
  tr:nth-child(even) { background: #f9fafb; }
  .badge-error { background: #fef2f2; color: #991b1b; border-radius: 4px; padding: 1px 6px; font-size: 0.8em; font-weight: bold; }
  .badge-warning { background: #fffbeb; color: #92400e; border-radius: 4px; padding: 1px 6px; font-size: 0.8em; font-weight: bold; }
  .badge-note { background: #eff6ff; color: #1e40af; border-radius: 4px; padding: 1px 6px; font-size: 0.8em; font-weight: bold; }
  .badge-ok { background: #f0fdf4; color: #166534; border-radius: 4px; padding: 1px 6px; font-size: 0.8em; }
  .badge-skip { background: #f3f4f6; color: #6b7280; border-radius: 4px; padding: 1px 6px; font-size: 0.8em; }
  .card { display: inline-block; background: #f3f4f6; border-radius: 8px; padding: 12px 20px; margin: 4px; text-align: center; }
  .card .num { font-size: 2em; font-weight: bold; }
  .card .label { font-size: 0.85em; color: #6b7280; }
  details { margin: 4px 0; }
  summary { cursor: pointer; font-weight: bold; }
  .finding { margin: 8px 0 8px 16px; padding: 8px; background: #f9fafb; border-left: 3px solid #d1d5db; }
  .finding.error { border-left-color: #ef4444; }
  .finding.warning { border-left-color: #f59e0b; }
  .finding.note { border-left-color: #3b82f6; }
  .filter-bar { margin: 1em 0; }
  .filter-bar label { margin-right: 12px; }
  a { color: #2563eb; }
  code { font-size: 0.9em; background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }
</style>
</head>
<body>
<h1>insecure-tree report</h1>
<p>
  <strong>Project:</strong> {{ report.project_path }}<br>
  <strong>Source:</strong> {{ report.source_adapter }}<br>
  <strong>Scanned:</strong> {{ report.scan_timestamp }}<br>
  <strong>insecure-tree:</strong> {{ report.insecure_tree_version }}
  {% if report.zizmor_version %}&nbsp;&nbsp;<strong>zizmor:</strong> {{ report.zizmor_version }}{% endif %}
</p>

<h2>Summary</h2>
<div>
  <div class="card"><div class="num">{{ report.summary.total_packages }}</div><div class="label">packages</div></div>
  <div class="card"><div class="num">{{ report.summary.packages_with_github }}</div><div class="label">with GitHub</div></div>
  <div class="card"><div class="num">{{ report.summary.repos_scanned }}</div><div class="label">scanned</div></div>
  <div class="card"><div class="num">{{ report.summary.repos_with_findings }}</div><div class="label">with findings</div></div>
  <div class="card" style="background:#fef2f2"><div class="num" style="color:#991b1b">{{ report.summary.findings_by_severity.get('error', 0) }}</div><div class="label">errors</div></div>
  <div class="card" style="background:#fffbeb"><div class="num" style="color:#92400e">{{ report.summary.findings_by_severity.get('warning', 0) }}</div><div class="label">warnings</div></div>
</div>

<h2>Packages</h2>
<div class="filter-bar">
  Filter:
  <label><input type="checkbox" id="f-error" checked onchange="filterRows()"> errors</label>
  <label><input type="checkbox" id="f-warning" checked onchange="filterRows()"> warnings</label>
  <label><input type="checkbox" id="f-note" checked onchange="filterRows()"> notes</label>
  <label><input type="checkbox" id="f-clean" checked onchange="filterRows()"> clean</label>
</div>
<table id="pkg-table">
<thead>
<tr>
  <th onclick="sortTable(0)">Package &#8597;</th>
  <th onclick="sortTable(1)">Repository &#8597;</th>
  <th onclick="sortTable(2)">Status &#8597;</th>
  <th onclick="sortTable(3)">Confidence &#8597;</th>
  <th>Findings</th>
</tr>
</thead>
<tbody>
{% for pkg in report.packages | sort(attribute='normalized_name') %}
{% set scan = pkg.scan %}
{% set repo = pkg.selected_repo %}
{% set sev_class = 'clean' %}
{% if scan and scan.finding_count > 0 %}
  {% if scan.findings_by_severity.get('error', 0) > 0 %}{% set sev_class = 'error' %}
  {% elif scan.findings_by_severity.get('warning', 0) > 0 %}{% set sev_class = 'warning' %}
  {% else %}{% set sev_class = 'note' %}{% endif %}
{% endif %}
<tr data-sev="{{ sev_class }}">
  <td><code>{{ pkg.name }}=={{ pkg.version }}</code></td>
  <td>
    {% if repo %}
      <a href="https://github.com/{{ repo.owner }}/{{ repo.repo }}" target="_blank">{{ repo.owner }}/{{ repo.repo }}</a>
      {% if scan and scan.commit_sha %}
      <br><small>@ {{ scan.repo_ref or '' }}</small>
      {% endif %}
    {% else %}-{% endif %}
  </td>
  <td>
    {% if scan %}
      {% if scan.status.value == 'scanned' %}<span class="badge-ok">scanned</span>
      {% elif scan.status.value == 'no_workflows' %}<span class="badge-skip">no workflows</span>
      {% elif scan.status.value == 'no_repo' %}<span class="badge-skip">no repo</span>
      {% else %}<span class="badge-skip">{{ scan.status.value }}</span>{% endif %}
    {% else %}<span class="badge-skip">no repo</span>{% endif %}
  </td>
  <td>
    {% if repo %}
      {% if repo.confidence.value == 'high' %}<span class="badge-ok">high</span>
      {% elif repo.confidence.value == 'medium' %}<span class="badge-warning">medium</span>
      {% else %}<span class="badge-skip">{{ repo.confidence.value }}</span>{% endif %}
    {% else %}-{% endif %}
  </td>
  <td>
    {% if scan and scan.findings %}
    <details>
      <summary>
        {% if scan.findings_by_severity.get('error', 0) %}<span class="badge-error">{{ scan.findings_by_severity.get('error', 0) }} error{{ 's' if scan.findings_by_severity.get('error', 0) != 1 else '' }}</span> {% endif %}
        {% if scan.findings_by_severity.get('warning', 0) %}<span class="badge-warning">{{ scan.findings_by_severity.get('warning', 0) }} warning{{ 's' if scan.findings_by_severity.get('warning', 0) != 1 else '' }}</span> {% endif %}
        {% if scan.findings_by_severity.get('note', 0) %}<span class="badge-note">{{ scan.findings_by_severity.get('note', 0) }} note{{ 's' if scan.findings_by_severity.get('note', 0) != 1 else '' }}</span>{% endif %}
      </summary>
      {% for f in scan.findings %}
      <div class="finding {{ f.severity }}">
        <strong>{{ f.rule_id }}</strong>: {{ f.title }}<br>
        <code>{{ f.path }}:{{ f.line }}</code><br>
        {{ f.message }}
        {% if f.url %}<br><a href="{{ f.url }}" target="_blank">View on GitHub</a>{% endif %}
      </div>
      {% endfor %}
    </details>
    {% elif scan and scan.status.value == 'scanned' %}
      <span class="badge-ok">clean</span>
    {% else %}-{% endif %}
  </td>
</tr>
{% endfor %}
</tbody>
</table>

<script>
function filterRows() {
  const showError = document.getElementById('f-error').checked;
  const showWarn = document.getElementById('f-warning').checked;
  const showNote = document.getElementById('f-note').checked;
  const showClean = document.getElementById('f-clean').checked;
  document.querySelectorAll('#pkg-table tbody tr').forEach(function(row) {
    const sev = row.getAttribute('data-sev');
    let show = false;
    if (sev === 'error' && showError) show = true;
    if (sev === 'warning' && showWarn) show = true;
    if (sev === 'note' && showNote) show = true;
    if (sev === 'clean' && showClean) show = true;
    row.style.display = show ? '' : 'none';
  });
}
function sortTable(col) {
  const table = document.getElementById('pkg-table');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const asc = table.getAttribute('data-sort-col') == col && table.getAttribute('data-sort-asc') == '1';
  rows.sort(function(a, b) {
    const at = a.cells[col] ? a.cells[col].textContent.trim() : '';
    const bt = b.cells[col] ? b.cells[col].textContent.trim() : '';
    return asc ? bt.localeCompare(at) : at.localeCompare(bt);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  table.setAttribute('data-sort-col', col);
  table.setAttribute('data-sort-asc', asc ? '0' : '1');
}
</script>
</body>
</html>
"""


def write_html(report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(autoescape=select_autoescape(["html"]))
    template = env.from_string(_TEMPLATE)
    html = template.render(report=report, ScanStatus=ScanStatus)
    path.write_text(html, encoding="utf-8")
