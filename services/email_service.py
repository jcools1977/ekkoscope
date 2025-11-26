import os
import subprocess
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime

REPLIT_CONNECTORS_HOSTNAME = os.getenv("REPLIT_CONNECTORS_HOSTNAME", "connectors.replit.com")


def get_replit_auth_token(hostname: str) -> str:
    try:
        result = subprocess.run(
            ["replit", "identity", "create", "--audience", f"https://{hostname}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        token = result.stdout.strip()
        if not token:
            raise Exception("Failed to get Replit identity token")
        return token
    except FileNotFoundError:
        raise Exception("Replit CLI not available - running outside of Replit environment")
    except subprocess.TimeoutExpired:
        raise Exception("Timeout while getting Replit identity token")


async def send_email(
    to: str | List[str],
    subject: str,
    text: Optional[str] = None,
    html: Optional[str] = None,
    cc: Optional[str | List[str]] = None
) -> Dict[str, Any]:
    hostname = REPLIT_CONNECTORS_HOSTNAME
    auth_token = get_replit_auth_token(hostname)
    
    payload = {
        "to": to,
        "subject": subject
    }
    
    if text:
        payload["text"] = text
    if html:
        payload["html"] = html
    if cc:
        payload["cc"] = cc
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{hostname}/api/v2/mailer/send",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Replit-Authentication": f"Bearer {auth_token}"
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            raise Exception(error_data.get("message", f"Email send failed: {response.status_code}"))
        
        return response.json()


async def send_welcome_email(email: str, first_name: str) -> bool:
    subject = "Welcome to EkkoScope - Discover Your AI Visibility"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #2EE6A8, #3B82F6); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .header h1 {{ color: white; margin: 0; font-size: 28px; }}
        .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #2EE6A8, #3B82F6); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>EkkoScope</h1>
        </div>
        <div class="content">
            <p>Hi {first_name},</p>
            <p>Welcome to EkkoScope! You've just taken the first step toward understanding how AI assistants see and recommend your business.</p>
            <p>With EkkoScope, you can:</p>
            <ul>
                <li>See exactly how ChatGPT and other AI describe your business</li>
                <li>Identify gaps in your AI visibility vs competitors</li>
                <li>Get actionable recommendations to improve your presence</li>
            </ul>
            <p>Ready to discover your AI visibility score?</p>
            <p style="text-align: center;">
                <a href="https://ekkoscope.com/dashboard" class="cta-button">Go to Dashboard</a>
            </p>
            <p>If you have any questions, just reply to this email.</p>
            <p>Best,<br>The EkkoScope Team</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} EkkoScope. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    text = f"""Hi {first_name},

Welcome to EkkoScope! You've just taken the first step toward understanding how AI assistants see and recommend your business.

With EkkoScope, you can:
- See exactly how ChatGPT and other AI describe your business
- Identify gaps in your AI visibility vs competitors
- Get actionable recommendations to improve your presence

Ready to discover your AI visibility score? Visit your dashboard: https://ekkoscope.com/dashboard

If you have any questions, just reply to this email.

Best,
The EkkoScope Team
"""
    
    try:
        await send_email(to=email, subject=subject, html=html, text=text)
        return True
    except Exception as e:
        print(f"Error sending welcome email to {email}: {e}")
        return False


async def send_followup_email(email: str, first_name: str, hours_since_signup: int = 24) -> bool:
    if hours_since_signup < 48:
        subject = "Still curious about your AI visibility? Here's a quick look"
        urgency = "Your business could be missing AI recommendations right now."
    else:
        subject = "Last chance: See how AI sees your business"
        urgency = "Don't let competitors capture the AI visibility you're missing."
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #2EE6A8, #3B82F6); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .header h1 {{ color: white; margin: 0; font-size: 28px; }}
        .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
        .highlight {{ background: #fff3cd; padding: 15px; border-radius: 6px; border-left: 4px solid #ffc107; margin: 20px 0; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #2EE6A8, #3B82F6); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>EkkoScope</h1>
        </div>
        <div class="content">
            <p>Hi {first_name},</p>
            <p>I noticed you signed up for EkkoScope but haven't run your first AI visibility audit yet.</p>
            <div class="highlight">
                <strong>{urgency}</strong>
            </div>
            <p>Here's what you'll discover in just 5 minutes:</p>
            <ul>
                <li>Your current AI visibility score</li>
                <li>How you compare to competitors in AI recommendations</li>
                <li>Specific content changes to boost your visibility</li>
            </ul>
            <p style="text-align: center;">
                <a href="https://ekkoscope.com/dashboard" class="cta-button">Run Your Audit Now</a>
            </p>
            <p>Questions? Just reply to this email.</p>
            <p>Best,<br>The EkkoScope Team</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} EkkoScope. All rights reserved.</p>
            <p><a href="https://ekkoscope.com/unsubscribe">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>
"""
    
    text = f"""Hi {first_name},

I noticed you signed up for EkkoScope but haven't run your first AI visibility audit yet.

{urgency}

Here's what you'll discover in just 5 minutes:
- Your current AI visibility score
- How you compare to competitors in AI recommendations
- Specific content changes to boost your visibility

Run your audit now: https://ekkoscope.com/dashboard

Questions? Just reply to this email.

Best,
The EkkoScope Team
"""
    
    try:
        await send_email(to=email, subject=subject, html=html, text=text)
        return True
    except Exception as e:
        print(f"Error sending follow-up email to {email}: {e}")
        return False


async def send_audit_complete_email(email: str, first_name: str, business_name: str, audit_id: int) -> bool:
    subject = f"Your AI Visibility Audit is Ready - {business_name}"
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #2EE6A8, #3B82F6); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .header h1 {{ color: white; margin: 0; font-size: 28px; }}
        .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
        .success-box {{ background: #d1fae5; padding: 15px; border-radius: 6px; border-left: 4px solid #10b981; margin: 20px 0; text-align: center; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #2EE6A8, #3B82F6); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>EkkoScope</h1>
        </div>
        <div class="content">
            <p>Hi {first_name},</p>
            <div class="success-box">
                <strong>Your AI Visibility Audit for {business_name} is complete!</strong>
            </div>
            <p>Your full report includes:</p>
            <ul>
                <li>AI visibility score and breakdown</li>
                <li>Competitor analysis</li>
                <li>Genius Insights with priority recommendations</li>
                <li>Downloadable PDF report</li>
            </ul>
            <p style="text-align: center;">
                <a href="https://ekkoscope.com/dashboard/audit/{audit_id}" class="cta-button">View Your Report</a>
            </p>
            <p>Thanks for using EkkoScope!</p>
            <p>Best,<br>The EkkoScope Team</p>
        </div>
        <div class="footer">
            <p>&copy; {datetime.now().year} EkkoScope. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    text = f"""Hi {first_name},

Great news! Your AI Visibility Audit for {business_name} is complete!

Your full report includes:
- AI visibility score and breakdown
- Competitor analysis
- Genius Insights with priority recommendations
- Downloadable PDF report

View your report: https://ekkoscope.com/dashboard/audit/{audit_id}

Thanks for using EkkoScope!

Best,
The EkkoScope Team
"""
    
    try:
        await send_email(to=email, subject=subject, html=html, text=text)
        return True
    except Exception as e:
        print(f"Error sending audit complete email to {email}: {e}")
        return False
