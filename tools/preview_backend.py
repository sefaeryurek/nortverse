"""Deterministic UI review data. Never connects to a database or external site.

Run with PYTHONPATH=backend python tools/preview_backend.py, then point a local
Next.js preview's BACKEND_URL at http://127.0.0.1:8011.
"""
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from app.analysis.pattern_stats import compute_stats
from app.db.models import Match

rows = [Match(actual_ft_home=2, actual_ft_away=i % 2, actual_ht_home=1, actual_ht_away=0,
              actual_h2_home=1, actual_h2_away=i % 2) for i in range(10)]
pattern = compute_stats(rows, "ft").model_dump()
match = dict(match_id="123", home_team="Örnek İstanbul Spor Kulübü", away_team="Örnek Ankara Spor Kulübü",
             league_code="TUR D1", league_name="Turkish Super Lig", kickoff_time=datetime.now(timezone.utc).isoformat())
analysis = dict(match, season="2026/2027", ht=dict(scores_1=["1-0"], scores_x=[], scores_2=[]),
                half2=dict(scores_1=["1-0"], scores_x=["1-1"], scores_2=[]),
                ft=dict(scores_1=["2-0", "2-1"], scores_x=[], scores_2=[]),
                ht_b=pattern, ht_c=pattern, h2_b=pattern, h2_c=pattern, ft_b=pattern, ft_c=pattern,
                trends=None, skipped=False, skip_reason=None)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/fixture":
            payload = [match]
        elif path == "/api/results":
            payload = [dict(match, status="pending", actual_ft_home=None, actual_ft_away=None,
                            actual_ht_home=None, actual_ht_away=None, result=None, kg_var=None,
                            over_25=None, katman_a_covered=None)]
        elif path == "/api/analyze/123":
            payload = analysis
        else:
            self.send_error(404)
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8011), Handler).serve_forever()
