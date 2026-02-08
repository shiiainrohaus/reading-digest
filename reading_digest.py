#!/usr/bin/env python3
"""
Reading Digest - Document Extraction & Google Sheets Automation
Extracts content from documents (PDF, EPUB, TXT) based on keywords,
writes to Google Sheets, and sends Discord alerts.
"""

import os
import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Google Sheets API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Document parsing
import PyPDF2
from ebooklib import epub
from bs4 import BeautifulSoup

# Discord alerts
import requests

# Token estimation
import tiktoken

# Configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CONFIG_PATH = Path(__file__).parent / 'config.json'
CREDENTIALS_PATH = Path(__file__).parent / 'credentials.json'
TOKEN_PATH = Path(__file__).parent / 'token.json'


class TokenMonitor:
    """Monitors and estimates token usage for budget control."""
    
    def __init__(self, max_budget: int = 50000, warning_threshold: float = 0.8):
        self.max_budget = max_budget
        self.warning_threshold = warning_threshold
        self.tokens_used = 0
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoder = None
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text."""
        if self.encoder:
            return len(self.encoder.encode(text))
        # Fallback: rough estimate (1 token ≈ 4 chars for English, 1.5 for Chinese)
        return len(text) // 2
    
    def add_usage(self, tokens: int) -> Tuple[bool, str]:
        """Add token usage and check budget. Returns (ok, message)."""
        self.tokens_used += tokens
        percentage = self.tokens_used / self.max_budget
        
        if percentage >= 1.0:
            return False, f"⛔ BUDGET EXCEEDED: {self.tokens_used}/{self.max_budget} tokens used. Task stopped."
        elif percentage >= self.warning_threshold:
            return True, f"⚠️ WARNING: {percentage*100:.1f}% of token budget used ({self.tokens_used}/{self.max_budget})"
        return True, ""
    
    def get_status(self) -> str:
        """Get current usage status."""
        percentage = (self.tokens_used / self.max_budget) * 100
        return f"📊 Token Usage: {self.tokens_used}/{self.max_budget} ({percentage:.1f}%)"


class DiscordAlerter:
    """Sends alerts to Discord webhooks."""
    
    def __init__(self, results_webhook: str = "", token_webhook: str = ""):
        self.results_webhook = results_webhook
        self.token_webhook = token_webhook
    
    def send_result(self, message: str, embed: Optional[Dict] = None):
        """Send alert to results thread."""
        self._send(self.results_webhook, message, embed)
    
    def send_token_alert(self, message: str, embed: Optional[Dict] = None):
        """Send alert to token/usage thread."""
        self._send(self.token_webhook, message, embed)
    
    def _send(self, webhook_url: str, message: str, embed: Optional[Dict] = None):
        """Internal send method."""
        if not webhook_url:
            print(f"[Discord Alert - No Webhook] {message}")
            return
        
        payload = {"content": message}
        if embed:
            payload["embeds"] = [embed]
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"[Discord Alert Error] {e}")


class DocumentParser:
    """Parses various document formats."""
    
    @staticmethod
    def parse(file_path: str) -> str:
        """Parse document and return text content."""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == '.txt':
            return DocumentParser._parse_txt(path)
        elif suffix == '.pdf':
            return DocumentParser._parse_pdf(path)
        elif suffix == '.epub':
            return DocumentParser._parse_epub(path)
        else:
            raise ValueError(f"Unsupported format: {suffix}")
    
    @staticmethod
    def _parse_txt(path: Path) -> str:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    @staticmethod
    def _parse_pdf(path: Path) -> str:
        text_parts = []
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text_parts.append(page.extract_text() or '')
        return '\n'.join(text_parts)
    
    @staticmethod
    def _parse_epub(path: Path) -> str:
        book = epub.read_epub(str(path))
        text_parts = []
        for item in book.get_items():
            if item.get_type() == 9:  # XHTML content
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text_parts.append(soup.get_text())
        return '\n'.join(text_parts)


class ContentExtractor:
    """Extracts content based on keywords."""
    
    def __init__(self, keywords: List[str], context_chars: int = 200):
        self.keywords = [kw.lower() for kw in keywords]
        self.context_chars = context_chars
    
    def extract(self, text: str, source: str = "", author: str = "") -> List[Dict]:
        """Extract matching content with context."""
        results = []
        text_lower = text.lower()
        seen_hashes = set()
        
        for keyword in self.keywords:
            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(keyword, start)
                if pos == -1:
                    break
                
                # Extract context around the keyword
                ctx_start = max(0, pos - self.context_chars)
                ctx_end = min(len(text), pos + len(keyword) + self.context_chars)
                content = text[ctx_start:ctx_end].strip()
                
                # Clean up content (find sentence boundaries if possible)
                content = self._clean_content(content)
                
                # Deduplicate by content hash
                content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
                if content_hash not in seen_hashes:
                    seen_hashes.add(content_hash)
                    results.append({
                        'Title': keyword.title(),
                        'Category': self._categorize(keyword),
                        'Tags': keyword,
                        'Content': content,
                        'Source': source,
                        'Author': author,
                        'Date Added': datetime.now().strftime('%Y-%m-%d'),
                        'Unique ID': content_hash,
                        'Notes': ''
                    })
                
                start = pos + 1
        
        return results
    
    def _clean_content(self, content: str) -> str:
        """Clean extracted content."""
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        # Trim to sentence boundaries if possible
        content = content.strip()
        if not content.startswith(('。', '！', '？', '.', '!', '?')):
            # Try to find start of sentence
            for sep in ['。', '！', '？', '.', '!', '?']:
                idx = content.find(sep)
                if idx != -1 and idx < 50:
                    content = content[idx+1:].strip()
                    break
        return content
    
    def _categorize(self, keyword: str) -> str:
        """Auto-categorize based on keyword patterns."""
        # Simple categorization - can be enhanced
        return "提取内容"


class GoogleSheetsClient:
    """Google Sheets API client."""
    
    def __init__(self, sheet_id: str, sheet_name: str = "Sheet1"):
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API."""
        creds = None
        
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('sheets', 'v4', credentials=creds)
    
    def setup_headers(self, headers: List[str]):
        """Set up header row if not exists."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f'{self.sheet_name}!A1:I1'
            ).execute()
            
            existing = result.get('values', [[]])[0]
            if existing != headers:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=f'{self.sheet_name}!A1:I1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                return True
        except HttpError as e:
            print(f"Error setting headers: {e}")
        return False
    
    def get_existing_ids(self) -> set:
        """Get existing Unique IDs to avoid duplicates."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f'{self.sheet_name}!H:H'
            ).execute()
            values = result.get('values', [])
            return {row[0] for row in values[1:] if row}  # Skip header
        except HttpError:
            return set()
    
    def append_rows(self, rows: List[Dict], headers: List[str]) -> int:
        """Append new rows to sheet. Returns count of added rows."""
        existing_ids = self.get_existing_ids()
        
        # Filter out duplicates
        new_rows = []
        for row in rows:
            if row.get('Unique ID') not in existing_ids:
                new_rows.append([row.get(h, '') for h in headers])
        
        if not new_rows:
            return 0
        
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f'{self.sheet_name}!A:I',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': new_rows}
            ).execute()
            return len(new_rows)
        except HttpError as e:
            print(f"Error appending rows: {e}")
            return 0


class ReadingDigest:
    """Main orchestrator for reading digest workflow."""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path or CONFIG_PATH)
        self.sheets = GoogleSheetsClient(
            self.config['sheet_id'],
            self.config.get('sheet_name', 'Sheet1')
        )
        self.alerter = DiscordAlerter(
            self.config.get('discord_webhook_results', ''),
            self.config.get('discord_webhook_token_alerts', '')
        )
        self.token_monitor = TokenMonitor(
            self.config.get('max_token_budget', 50000),
            self.config.get('token_warning_threshold', 0.8)
        )
        self.headers = self.config['headers']
    
    def _load_config(self, path) -> Dict:
        with open(path, 'r') as f:
            return json.load(f)
    
    def estimate_task(self, file_path: str) -> Tuple[int, str]:
        """Estimate token usage for a document before processing."""
        try:
            text = DocumentParser.parse(file_path)
            tokens = self.token_monitor.estimate_tokens(text)
            file_size = Path(file_path).stat().st_size / 1024  # KB
            
            msg = (f"📄 **Task Estimation**\n"
                   f"- File: {Path(file_path).name}\n"
                   f"- Size: {file_size:.1f} KB\n"
                   f"- Estimated tokens: {tokens}\n"
                   f"- Budget: {self.token_monitor.max_budget}\n"
                   f"- Status: {'✅ Within budget' if tokens < self.token_monitor.max_budget else '⚠️ May exceed budget'}")
            
            self.alerter.send_token_alert(msg)
            return tokens, msg
        except Exception as e:
            return 0, f"❌ Estimation failed: {e}"
    
    def process_document(
        self,
        file_path: str,
        keywords: List[str],
        source: str = "",
        author: str = "",
        require_approval: bool = True
    ) -> Dict:
        """
        Process a document: extract content, write to sheet, send alerts.
        Returns summary of the operation.
        """
        result = {
            'success': False,
            'entries_found': 0,
            'entries_added': 0,
            'tokens_used': 0,
            'message': ''
        }
        
        # Step 1: Notify start
        self.alerter.send_result(f"🚀 **Starting extraction**\n- File: {Path(file_path).name}\n- Keywords: {', '.join(keywords)}")
        
        # Step 2: Parse document
        try:
            text = DocumentParser.parse(file_path)
            tokens = self.token_monitor.estimate_tokens(text)
            result['tokens_used'] = tokens
        except Exception as e:
            result['message'] = f"❌ Failed to parse document: {e}"
            self.alerter.send_result(result['message'])
            return result
        
        # Step 3: Check token budget
        ok, budget_msg = self.token_monitor.add_usage(tokens)
        if budget_msg:
            self.alerter.send_token_alert(budget_msg)
        if not ok:
            result['message'] = budget_msg
            return result
        
        # Step 4: Extract content
        extractor = ContentExtractor(keywords)
        entries = extractor.extract(text, source=source or Path(file_path).name, author=author)
        result['entries_found'] = len(entries)
        
        self.alerter.send_result(f"📝 Found {len(entries)} matching entries")
        
        # Step 5: Write to sheet
        self.sheets.setup_headers(self.headers)
        added = self.sheets.append_rows(entries, self.headers)
        result['entries_added'] = added
        
        # Step 6: Final notification
        result['success'] = True
        result['message'] = (f"✅ **Extraction Complete**\n"
                            f"- Entries found: {len(entries)}\n"
                            f"- New entries added: {added}\n"
                            f"- Duplicates skipped: {len(entries) - added}\n"
                            f"- {self.token_monitor.get_status()}\n\n"
                            f"📋 **Please review your Google Sheet:**\n"
                            f"https://docs.google.com/spreadsheets/d/{self.config['sheet_id']}")
        
        self.alerter.send_result(result['message'])
        self.alerter.send_token_alert(self.token_monitor.get_status())
        
        return result


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reading Digest - Extract content to Google Sheets')
    parser.add_argument('file', help='Document file path (PDF, EPUB, TXT)')
    parser.add_argument('-k', '--keywords', required=True, nargs='+', help='Keywords to search for')
    parser.add_argument('-s', '--source', default='', help='Source/book name')
    parser.add_argument('-a', '--author', default='', help='Author name')
    parser.add_argument('--estimate-only', action='store_true', help='Only estimate tokens, do not process')
    
    args = parser.parse_args()
    
    digest = ReadingDigest()
    
    if args.estimate_only:
        tokens, msg = digest.estimate_task(args.file)
        print(msg)
    else:
        result = digest.process_document(
            args.file,
            args.keywords,
            source=args.source,
            author=args.author
        )
        print(result['message'])


if __name__ == '__main__':
    main()
