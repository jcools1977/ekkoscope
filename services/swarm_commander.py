"""
Swarm Commander - Domain Procurement & DNS Automation Engine

Automates the "4-Step Handshake" for domain infrastructure:
1. BUY: Purchase domain via Namecheap API
2. HANDOVER: Create Cloudflare zone and get nameservers
3. LINK: Update Namecheap nameservers to Cloudflare
4. FORTIFY: Inject SPF, DKIM, DMARC security records

Prerequisites:
- Namecheap API Key (whitelist Replit IP in Namecheap dashboard)
- Cloudflare API Token (Zone:Edit and DNS:Edit permissions)
"""

import os
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
import tldextract
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class SwarmConfigError(Exception):
    """Raised when required configuration is missing."""
    pass

NAMECHEAP_USER = os.environ.get("NAMECHEAP_USER", "")
NAMECHEAP_KEY = os.environ.get("NAMECHEAP_API_KEY", "")
NAMECHEAP_CLIENT_IP = os.environ.get("NAMECHEAP_CLIENT_IP", "")
CLOUDFLARE_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

REGISTRANT_INFO = {
    "FirstName": os.environ.get("REGISTRANT_FIRST_NAME", ""),
    "LastName": os.environ.get("REGISTRANT_LAST_NAME", ""),
    "Address1": os.environ.get("REGISTRANT_ADDRESS", ""),
    "City": os.environ.get("REGISTRANT_CITY", ""),
    "StateProvince": os.environ.get("REGISTRANT_STATE", ""),
    "PostalCode": os.environ.get("REGISTRANT_ZIP", ""),
    "Country": os.environ.get("REGISTRANT_COUNTRY", "US"),
    "Phone": os.environ.get("REGISTRANT_PHONE", ""),
    "EmailAddress": os.environ.get("REGISTRANT_EMAIL", ""),
}


@dataclass
class DomainProvisionResult:
    """Result of a domain provisioning operation."""
    success: bool
    domain: str
    zone_id: Optional[str] = None
    nameservers: Optional[List[str]] = None
    records_added: int = 0
    error: Optional[str] = None
    steps_completed: List[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if self.steps_completed is None:
            self.steps_completed = []
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "domain": self.domain,
            "zone_id": self.zone_id,
            "nameservers": self.nameservers,
            "records_added": self.records_added,
            "error": self.error,
            "steps_completed": self.steps_completed,
            "timestamp": self.timestamp
        }


class SwarmCommander:
    """
    Infrastructure-as-Code engine for automated domain provisioning.
    
    Chains Namecheap (registrar) and Cloudflare (DNS/security) APIs
    to fully provision a cold email domain in ~15 seconds.
    """
    
    def __init__(self):
        self.nc_base = "https://api.namecheap.com/xml.response"
        self.cf_base = "https://api.cloudflare.com/client/v4"
        self.cf_headers = {
            "Authorization": f"Bearer {CLOUDFLARE_TOKEN}",
            "Content-Type": "application/json"
        }
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate that required secrets are configured."""
        missing = []
        if not NAMECHEAP_USER:
            missing.append("NAMECHEAP_USER")
        if not NAMECHEAP_KEY:
            missing.append("NAMECHEAP_API_KEY")
        if not CLOUDFLARE_TOKEN:
            missing.append("CLOUDFLARE_API_TOKEN")
        if not CLOUDFLARE_ACCOUNT_ID:
            missing.append("CLOUDFLARE_ACCOUNT_ID")
        
        if missing:
            logger.warning(f"[SWARM] Missing secrets: {', '.join(missing)}")
    
    def require_namecheap_config(self) -> None:
        """Raise error if Namecheap API is not configured."""
        missing = []
        if not NAMECHEAP_USER:
            missing.append("NAMECHEAP_USER")
        if not NAMECHEAP_KEY:
            missing.append("NAMECHEAP_API_KEY")
        if missing:
            raise SwarmConfigError(f"Namecheap API not configured: missing {', '.join(missing)}")
    
    def require_cloudflare_config(self) -> None:
        """Raise error if Cloudflare API is not configured."""
        missing = []
        if not CLOUDFLARE_TOKEN:
            missing.append("CLOUDFLARE_API_TOKEN")
        if not CLOUDFLARE_ACCOUNT_ID:
            missing.append("CLOUDFLARE_ACCOUNT_ID")
        if missing:
            raise SwarmConfigError(f"Cloudflare API not configured: missing {', '.join(missing)}")
    
    def _parse_domain(self, domain: str) -> Tuple[str, str]:
        """Parse domain into SLD and TLD components using tldextract."""
        domain = domain.lower().strip()
        domain = re.sub(r'^https?://', '', domain)
        domain = domain.split('/')[0]
        domain = domain.split(':')[0]
        
        extracted = tldextract.extract(domain)
        
        if not extracted.domain or not extracted.suffix:
            raise ValueError(f"Invalid domain format: {domain}")
        
        if extracted.subdomain:
            sld = f"{extracted.subdomain}.{extracted.domain}"
        else:
            sld = extracted.domain
        
        tld = extracted.suffix
        
        return sld, tld
    
    def check_availability(self, domain: str, require_config: bool = False) -> Dict[str, Any]:
        """
        Check if a domain is available for registration.
        
        Args:
            domain: The domain to check (e.g., "try-ekkoscope.com")
            require_config: If True, raise error if config missing
        
        Returns:
            Dict with availability status
        """
        logger.info(f"[SWARM] Checking availability: {domain}")
        
        if require_config:
            self.require_namecheap_config()
        elif not NAMECHEAP_KEY:
            return {"available": False, "error": "Namecheap API not configured"}
        
        try:
            sld, tld = self._parse_domain(domain)
            
            params = {
                "ApiUser": NAMECHEAP_USER,
                "ApiKey": NAMECHEAP_KEY,
                "UserName": NAMECHEAP_USER,
                "Command": "namecheap.domains.check",
                "ClientIp": NAMECHEAP_CLIENT_IP or self._get_public_ip(),
                "DomainList": domain
            }
            
            resp = requests.get(self.nc_base, params=params, timeout=30)
            
            if resp.status_code != 200:
                return {"available": False, "error": f"HTTP {resp.status_code}"}
            
            root = ET.fromstring(resp.text)
            
            ns = {"nc": "http://api.namecheap.com/xml.response"}
            domain_check = root.find(".//nc:DomainCheckResult", ns)
            
            if domain_check is not None:
                available = domain_check.get("Available", "false").lower() == "true"
                premium = domain_check.get("IsPremiumName", "false").lower() == "true"
                price = domain_check.get("PremiumRegistrationPrice", "")
                
                return {
                    "domain": domain,
                    "available": available,
                    "premium": premium,
                    "price": price if premium else None,
                    "error": None
                }
            
            return {"available": False, "error": "Could not parse response"}
            
        except Exception as e:
            logger.error(f"[SWARM] Availability check failed: {e}")
            return {"available": False, "error": str(e)}
    
    def buy_domain(self, domain: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Purchase a domain via Namecheap API.
        
        Args:
            domain: The domain to purchase
            dry_run: If True, simulate purchase without charging
        
        Returns:
            Dict with purchase result
        """
        logger.info(f"[SWARM] {'[DRY RUN] ' if dry_run else ''}Purchasing: {domain}")
        
        if dry_run:
            logger.info(f"[SWARM] DRY RUN - Would purchase {domain}")
            return {
                "success": True,
                "domain": domain,
                "dry_run": True,
                "message": f"DRY RUN: {domain} would be purchased"
            }
        
        if not NAMECHEAP_KEY:
            return {"success": False, "error": "Namecheap API not configured"}
        
        if not all(REGISTRANT_INFO.values()):
            return {"success": False, "error": "Registrant contact info incomplete"}
        
        try:
            sld, tld = self._parse_domain(domain)
            
            params = {
                "ApiUser": NAMECHEAP_USER,
                "ApiKey": NAMECHEAP_KEY,
                "UserName": NAMECHEAP_USER,
                "Command": "namecheap.domains.create",
                "ClientIp": NAMECHEAP_CLIENT_IP or self._get_public_ip(),
                "DomainName": domain,
                "Years": "1",
            }
            
            for prefix in ["Registrant", "Tech", "Admin", "AuxBilling"]:
                for key, value in REGISTRANT_INFO.items():
                    params[f"{prefix}{key}"] = value
            
            resp = requests.post(self.nc_base, params=params, timeout=60)
            
            if "IsSuccess=\"true\"" in resp.text:
                logger.info(f"[SWARM] Successfully purchased: {domain}")
                return {
                    "success": True,
                    "domain": domain,
                    "dry_run": False,
                    "message": f"Domain {domain} purchased successfully"
                }
            else:
                error_match = re.search(r'<Error[^>]*>(.*?)</Error>', resp.text)
                error_msg = error_match.group(1) if error_match else "Unknown error"
                logger.error(f"[SWARM] Purchase failed: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            logger.error(f"[SWARM] Purchase error: {e}")
            return {"success": False, "error": str(e)}
    
    def create_cloudflare_zone(self, domain: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """
        Create a zone in Cloudflare for the domain.
        
        Args:
            domain: The domain to add to Cloudflare
        
        Returns:
            Tuple of (zone_id, nameservers) or (None, None) on failure
        """
        logger.info(f"[SWARM] Creating Cloudflare zone: {domain}")
        
        if not CLOUDFLARE_TOKEN:
            logger.error("[SWARM] Cloudflare API not configured")
            return None, None
        
        try:
            url = f"{self.cf_base}/zones"
            data = {
                "name": domain,
                "account": {"id": CLOUDFLARE_ACCOUNT_ID},
                "type": "full"
            }
            
            resp = requests.post(url, headers=self.cf_headers, json=data, timeout=30)
            result = resp.json()
            
            if resp.status_code == 200 and result.get("success"):
                zone_data = result["result"]
                zone_id = zone_data["id"]
                nameservers = zone_data.get("name_servers", [])
                
                logger.info(f"[SWARM] Zone created: {zone_id}")
                logger.info(f"[SWARM] Nameservers: {nameservers}")
                
                return zone_id, nameservers
            else:
                errors = result.get("errors", [])
                error_msg = errors[0].get("message") if errors else "Unknown error"
                
                if "already exists" in error_msg.lower():
                    logger.info(f"[SWARM] Zone already exists, fetching...")
                    return self._get_existing_zone(domain)
                
                logger.error(f"[SWARM] Cloudflare zone creation failed: {error_msg}")
                return None, None
                
        except Exception as e:
            logger.error(f"[SWARM] Cloudflare error: {e}")
            return None, None
    
    def _get_existing_zone(self, domain: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """Fetch an existing Cloudflare zone."""
        try:
            url = f"{self.cf_base}/zones"
            params = {"name": domain}
            
            resp = requests.get(url, headers=self.cf_headers, params=params, timeout=30)
            result = resp.json()
            
            if result.get("success") and result.get("result"):
                zone = result["result"][0]
                return zone["id"], zone.get("name_servers", [])
            
            return None, None
            
        except Exception as e:
            logger.error(f"[SWARM] Failed to fetch existing zone: {e}")
            return None, None
    
    def set_nameservers(self, domain: str, nameservers: List[str]) -> bool:
        """
        Update domain nameservers in Namecheap to point to Cloudflare.
        
        Args:
            domain: The domain to update
            nameservers: List of Cloudflare nameservers
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"[SWARM] Setting nameservers for {domain}: {nameservers}")
        
        if not NAMECHEAP_KEY:
            logger.error("[SWARM] Namecheap API not configured")
            return False
        
        try:
            sld, tld = self._parse_domain(domain)
            
            params = {
                "ApiUser": NAMECHEAP_USER,
                "ApiKey": NAMECHEAP_KEY,
                "UserName": NAMECHEAP_USER,
                "Command": "namecheap.domains.dns.setCustom",
                "ClientIp": NAMECHEAP_CLIENT_IP or self._get_public_ip(),
                "SLD": sld,
                "TLD": tld,
                "Nameservers": ",".join(nameservers)
            }
            
            resp = requests.post(self.nc_base, params=params, timeout=30)
            
            if "IsSuccess=\"true\"" in resp.text:
                logger.info(f"[SWARM] Nameservers updated successfully")
                return True
            else:
                error_match = re.search(r'<Error[^>]*>(.*?)</Error>', resp.text)
                error_msg = error_match.group(1) if error_match else "Unknown error"
                logger.error(f"[SWARM] Nameserver update failed: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[SWARM] Nameserver update error: {e}")
            return False
    
    def inject_security_records(
        self, 
        zone_id: str, 
        email_provider: str = "google",
        dkim_value: Optional[str] = None
    ) -> int:
        """
        Add SPF, DKIM, and DMARC security records to Cloudflare zone.
        
        Args:
            zone_id: The Cloudflare zone ID
            email_provider: Email provider ("google", "microsoft", "instantly")
            dkim_value: Optional DKIM record value
        
        Returns:
            Number of records successfully added
        """
        logger.info(f"[SWARM] Injecting security records into zone {zone_id}")
        
        if not CLOUDFLARE_TOKEN:
            logger.error("[SWARM] Cloudflare API not configured")
            return 0
        
        spf_includes = {
            "google": "include:_spf.google.com",
            "microsoft": "include:spf.protection.outlook.com",
            "instantly": "include:_spf.instantly.ai"
        }
        
        spf_include = spf_includes.get(email_provider, spf_includes["google"])
        
        records = [
            {
                "type": "TXT",
                "name": "@",
                "content": f"v=spf1 {spf_include} ~all",
                "ttl": 3600,
                "comment": "SPF Record - Email authentication"
            },
            {
                "type": "TXT",
                "name": "_dmarc",
                "content": f"v=DMARC1; p=quarantine; rua=mailto:{REGISTRANT_INFO.get('EmailAddress', 'admin@example.com')}",
                "ttl": 3600,
                "comment": "DMARC Policy - Anti-spoofing"
            }
        ]
        
        if dkim_value:
            records.append({
                "type": "TXT",
                "name": "google._domainkey",
                "content": dkim_value,
                "ttl": 3600,
                "comment": "DKIM Record - Email signature"
            })
        
        added = 0
        for record in records:
            try:
                url = f"{self.cf_base}/zones/{zone_id}/dns_records"
                resp = requests.post(url, headers=self.cf_headers, json=record, timeout=30)
                result = resp.json()
                
                if result.get("success"):
                    logger.info(f"[SWARM] Added {record['type']} record: {record['name']}")
                    added += 1
                else:
                    errors = result.get("errors", [])
                    if any("already exists" in str(e).lower() for e in errors):
                        logger.info(f"[SWARM] Record already exists: {record['name']}")
                        added += 1
                    else:
                        logger.warning(f"[SWARM] Failed to add record: {errors}")
                        
            except Exception as e:
                logger.error(f"[SWARM] Error adding record: {e}")
        
        return added
    
    def add_mx_records(self, zone_id: str, provider: str = "google") -> int:
        """
        Add MX records for email delivery.
        
        Args:
            zone_id: The Cloudflare zone ID
            provider: Email provider ("google", "microsoft")
        
        Returns:
            Number of MX records added
        """
        logger.info(f"[SWARM] Adding MX records for {provider}")
        
        mx_configs = {
            "google": [
                {"name": "@", "content": "aspmx.l.google.com", "priority": 1},
                {"name": "@", "content": "alt1.aspmx.l.google.com", "priority": 5},
                {"name": "@", "content": "alt2.aspmx.l.google.com", "priority": 5},
            ],
            "microsoft": [
                {"name": "@", "content": "your-domain.mail.protection.outlook.com", "priority": 0},
            ]
        }
        
        records = mx_configs.get(provider, mx_configs["google"])
        added = 0
        
        for mx in records:
            try:
                url = f"{self.cf_base}/zones/{zone_id}/dns_records"
                data = {
                    "type": "MX",
                    "name": mx["name"],
                    "content": mx["content"],
                    "priority": mx["priority"],
                    "ttl": 3600
                }
                
                resp = requests.post(url, headers=self.cf_headers, json=data, timeout=30)
                if resp.json().get("success"):
                    added += 1
                    
            except Exception as e:
                logger.error(f"[SWARM] MX record error: {e}")
        
        return added
    
    def provision_domain(
        self,
        domain: str,
        dry_run: bool = True,
        email_provider: str = "google",
        skip_purchase: bool = False
    ) -> DomainProvisionResult:
        """
        Execute the full 4-step domain provisioning handshake.
        
        Args:
            domain: Domain to provision (e.g., "try-ekkoscope.com")
            dry_run: If True, simulate purchase step
            email_provider: Email provider for DNS records
            skip_purchase: If True, skip purchase (domain already owned)
        
        Returns:
            DomainProvisionResult with full status
        """
        logger.info(f"[SWARM] === INITIATING DOMAIN PROVISION: {domain} ===")
        
        result = DomainProvisionResult(
            success=False,
            domain=domain
        )
        
        try:
            if not skip_purchase:
                purchase = self.buy_domain(domain, dry_run=dry_run)
                if not purchase.get("success"):
                    result.error = purchase.get("error", "Purchase failed")
                    return result
                result.steps_completed.append("PURCHASE" if not dry_run else "PURCHASE_SIMULATED")
            else:
                result.steps_completed.append("PURCHASE_SKIPPED")
            
            zone_id, nameservers = self.create_cloudflare_zone(domain)
            if not zone_id:
                result.error = "Failed to create Cloudflare zone"
                return result
            
            result.zone_id = zone_id
            result.nameservers = nameservers
            result.steps_completed.append("CLOUDFLARE_ZONE_CREATED")
            
            if nameservers and not skip_purchase:
                ns_success = self.set_nameservers(domain, nameservers)
                if ns_success:
                    result.steps_completed.append("NAMESERVERS_UPDATED")
                else:
                    logger.warning("[SWARM] Nameserver update failed, continuing...")
            
            records_added = self.inject_security_records(zone_id, email_provider)
            result.records_added = records_added
            result.steps_completed.append(f"SECURITY_RECORDS_ADDED_{records_added}")
            
            result.success = True
            logger.info(f"[SWARM] === PROVISION COMPLETE: {domain} ===")
            
        except Exception as e:
            logger.error(f"[SWARM] Provision failed: {e}")
            result.error = str(e)
        
        return result
    
    def _get_public_ip(self) -> str:
        """Get the current public IP address."""
        try:
            resp = requests.get("https://api.ipify.org", timeout=10)
            return resp.text.strip()
        except Exception:
            return ""
    
    def get_zone_status(self, domain: str) -> Dict[str, Any]:
        """
        Get the current status of a domain in Cloudflare.
        
        Args:
            domain: The domain to check
        
        Returns:
            Dict with zone status and DNS records
        """
        try:
            zone_id, nameservers = self._get_existing_zone(domain)
            
            if not zone_id:
                return {"exists": False, "domain": domain}
            
            url = f"{self.cf_base}/zones/{zone_id}/dns_records"
            resp = requests.get(url, headers=self.cf_headers, timeout=30)
            result = resp.json()
            
            records = []
            if result.get("success"):
                for rec in result.get("result", []):
                    records.append({
                        "type": rec["type"],
                        "name": rec["name"],
                        "content": rec["content"][:100]
                    })
            
            return {
                "exists": True,
                "domain": domain,
                "zone_id": zone_id,
                "nameservers": nameservers,
                "records": records
            }
            
        except Exception as e:
            logger.error(f"[SWARM] Status check failed: {e}")
            return {"exists": False, "error": str(e)}


def get_swarm_commander() -> SwarmCommander:
    """Get a configured SwarmCommander instance."""
    return SwarmCommander()
