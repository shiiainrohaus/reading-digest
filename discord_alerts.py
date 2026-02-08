#!/usr/bin/env python3
"""
Discord Alert Helper for Reading Digest
Sends alerts to the designated Discord threads.

This module can be used standalone or imported by reading_digest.py
"""

import json
import requests
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent / 'config.json'

# Discord Bot Token (if using bot API instead of webhooks)
# For webhook-based alerts, configure webhook URLs in config.json
# For bot-based alerts, this script can be extended


class DiscordThreadAlerter:
    """
    Sends messages to Discord threads.
    
    Can work in two modes:
    1. Webhook mode: Use webhook URLs (simpler, no bot needed)
    2. Bot mode: Use bot token to post to threads (more flexible)
    
    For now, implements webhook mode. Bot mode can be added if needed.
    """
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path or CONFIG_PATH)
        self.extraction_thread_id = self.config.get('discord_thread_extraction', '')
        self.token_thread_id = self.config.get('discord_thread_token_safety', '')
        self.results_webhook = self.config.get('discord_webhook_results', '')
        self.token_webhook = self.config.get('discord_webhook_token_alerts', '')
    
    def _load_config(self, path) -> dict:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def send_extraction_alert(self, message: str, embed: Optional[dict] = None):
        """Send alert to Extraction Workflow thread."""
        self._send_webhook(self.results_webhook, message, embed, self.extraction_thread_id)
    
    def send_token_alert(self, message: str, embed: Optional[dict] = None):
        """Send alert to Token Safety thread."""
        self._send_webhook(self.token_webhook, message, embed, self.token_thread_id)
    
    def _send_webhook(self, webhook_url: str, message: str, embed: Optional[dict] = None, thread_id: str = ""):
        """Send message via webhook."""
        if not webhook_url:
            print(f"[Discord Alert - No Webhook] {message}")
            return False
        
        payload = {"content": message}
        if embed:
            payload["embeds"] = [embed]
        
        # If posting to a thread, append thread_id to webhook URL
        url = webhook_url
        if thread_id:
            separator = '&' if '?' in webhook_url else '?'
            url = f"{webhook_url}{separator}thread_id={thread_id}"
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[Discord Alert Error] {e}")
            return False


def send_extraction_alert(message: str):
    """Quick function to send extraction alert."""
    alerter = DiscordThreadAlerter()
    alerter.send_extraction_alert(message)


def send_token_alert(message: str):
    """Quick function to send token alert."""
    alerter = DiscordThreadAlerter()
    alerter.send_token_alert(message)


# Example usage and thread info
if __name__ == '__main__':
    print("Discord Thread Alert Helper")
    print("=" * 40)
    print()
    print("Thread IDs configured:")
    alerter = DiscordThreadAlerter()
    print(f"  Extraction Workflow: {alerter.extraction_thread_id}")
    print(f"  Token Safety: {alerter.token_thread_id}")
    print()
    print("To use webhooks, add your webhook URLs to config.json:")
    print('  "discord_webhook_results": "https://discord.com/api/webhooks/..."')
    print('  "discord_webhook_token_alerts": "https://discord.com/api/webhooks/..."')
    print()
    print("HOW TO CREATE WEBHOOKS:")
    print("1. Go to your Discord server")
    print("2. Right-click the 'reading-digest-gsheet' channel")
    print("3. Edit Channel → Integrations → Webhooks")
    print("4. Create Webhook → Copy URL")
    print("5. Add URL to config.json")
    print()
    print("The script will automatically post to the correct thread using thread_id parameter.")
