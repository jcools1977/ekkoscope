"""
================================================================================
  SENTINEL_OS INTEGRATION FOR EKKOSCOPE
================================================================================
"""
import os
import json
import hashlib
import functools
from datetime import datetime
from typing import Optional, Dict, Any, Callable
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
class SentinelClient:
    def __init__(
        self, 
        api_key: str = None,
        base_url: str = "https://sentinelos.an2b.com",
        agent_id: str = "ekkoscope-agent",
        fail_open: bool = True,
        verbose: bool = True
    ):
        self.api_key = api_key or os.environ.get("SENTINEL_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.fail_open = fail_open
        self.verbose = verbose
        self.run_id = f"ekko_{int(datetime.utcnow().timestamp())}_{os.urandom(4).hex()}"
        self._sequence = 0
        self._last_hash = "0" * 64
        if self.verbose and self.api_key:
            print(f"[SENTINEL] Connected: {self.api_key[:16]}...")
    def _compute_hash(self, data: Dict) -> str:
        payload = json.dumps(data, sort_keys=True, default=str) + self._last_hash
        self._last_hash = hashlib.sha256(payload.encode()).hexdigest()
        return self._last_hash
    def _request(self, endpoint: str, payload: Dict) -> Dict:
        if not self.api_key:
            return {"decision": "allow", "reason": "no_api_key"}
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "EkkoScope-Sentinel/1.0"
        }
        try:
            if HAS_REQUESTS:
                resp = requests.post(url, json=payload, headers=headers, timeout=5)
                return resp.json()
            else:
                data = json.dumps(payload).encode()
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return json.loads(resp.read().decode())
        except Exception as e:
            if self.verbose:
                print(f"[SENTINEL] Request error: {e}")
            if self.fail_open:
                return {"decision": "allow", "reason": "network_error", "error": str(e)}
            raise
    def check_action(self, action: Dict, context: Dict = None) -> Dict:
        self._sequence += 1
        event = {
            "action": action,
            "context": context or {},
            "agent_id": self.agent_id,
            "run_id": self.run_id,
            "sequence": self._sequence,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        event["hash"] = self._compute_hash(event)
        result = self._request("/api/ingest", event)
        if self.verbose:
            decision = result.get("decision", "unknown")
            action_type = action.get("type", "unknown")
            print(f"[SENTINEL] {action_type} -> {decision}")
        return result
    def log_event(self, event_type: str, data: Dict = None) -> Dict:
        action = {"type": event_type}
        if data:
            action.update(data)
        return self.check_action(action, {"eventOnly": True})
sentinel = SentinelClient()
def log_ai_query(model: str, prompt: str, business_name: str = None, tokens: int = None):
    """Log an AI query (ChatGPT, Gemini, Perplexity, etc.)"""
    sentinel.log_event("ai.query", {
        "model": model,
        "prompt_preview": prompt[:150] if prompt else None,
        "business_name": business_name,
        "tokens": tokens
    })
def log_report_generated(business_name: str, report_type: str = "geo_report", pages: int = 19):
    """Log when a GEO report is generated"""
    sentinel.log_event("report.generated", {
        "business_name": business_name,
        "report_type": report_type,
        "pages": pages
    })
def log_visibility_score(business_name: str, score: float, ai_models: list = None):
    """Log visibility score calculation"""
    sentinel.log_event("visibility.calculated", {
        "business_name": business_name,
        "visibility_score": score,
        "ai_models": ai_models or ["chatgpt", "gemini", "perplexity"]
    })
def log_competitor_analysis(business_name: str, competitors: list, industry: str = None):
    """Log competitor analysis"""
    sentinel.log_event("analysis.competitors", {
        "business_name": business_name,
        "competitor_count": len(competitors),
        "top_competitors": competitors[:5],
        "industry": industry
    })
def log_user_signup(email: str, plan: str = "free", source: str = "website"):
    """Log user signup"""
    sentinel.log_event("user.signup", {
        "email_domain": email.split("@")[-1] if "@" in email else None,
        "plan": plan,
        "source": source
    })
def log_payment(amount: float, currency: str = "usd", product: str = None):
    """Log payment event"""
    sentinel.log_event("payment.completed", {
        "amount": amount,
        "currency": currency,
        "product": product
    })
