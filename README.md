# Reading Digest

Automated document extraction & Google Sheets sync tool.

Extracts content from books/documents (PDF, EPUB, TXT) based on keywords, writes results to Google Sheets, and sends Discord alerts for workflow tracking.

## Features

- **Multi-format support**: PDF, EPUB, TXT
- **Keyword-based extraction**: Find and extract content matching your requirements
- **Auto-tagging & categorization**: Organize extracted content
- **Deduplication**: Prevents duplicate entries
- **Token budget monitoring**: Estimates and tracks usage before/during extraction
- **Discord alerts**: Two-thread workflow for results and token/usage alerts
- **Google Sheets integration**: Writes directly to your sheet

## Setup

### 1. Install Dependencies

```bash
cd reading-digest
pip install -r requirements.txt
```

### 2. Configure Google Sheets API

- Credentials file (`credentials.json`) is already set up
- On first run, you'll be prompted to authorize access via browser
- Token will be saved for future use

### 3. Configure Discord Webhooks (Optional)

Edit `config.json` and add your webhook URLs:

```json
{
  "discord_webhook_results": "https://discord.com/api/webhooks/...",
  "discord_webhook_token_alerts": "https://discord.com/api/webhooks/..."
}
```

#### How to Create Discord Webhooks:

1. In Discord, go to your server
2. Create two threads:
   - **Extraction Workflow** (for task results)
   - **Token Safety** (for usage alerts)
3. For each thread/channel:
   - Right-click → Edit Channel → Integrations → Webhooks
   - Create Webhook → Copy URL
4. Paste URLs into `config.json`

### 4. Set Token Budget

In `config.json`:

```json
{
  "max_token_budget": 50000,
  "token_warning_threshold": 0.8
}
```

## Usage

### Estimate Token Usage (Before Processing)

```bash
python reading_digest.py document.pdf -k keyword1 keyword2 --estimate-only
```

### Extract Content

```bash
python reading_digest.py document.pdf -k "意象" "典故" -s "Book Name" -a "Author"
```

### Options

- `file`: Document path (PDF, EPUB, TXT)
- `-k, --keywords`: Keywords to search for (required)
- `-s, --source`: Source/book name
- `-a, --author`: Author name
- `--estimate-only`: Only estimate tokens, don't process

## Workflow

1. **You provide**: Book/document + keywords
2. **Script estimates**: Token usage, requests approval if needed
3. **Script extracts**: Finds matching content, tags, deduplicates
4. **Script writes**: Adds entries to Google Sheet
5. **Script alerts**: Sends Discord notification for review
6. **You review**: Edit/remove unwanted entries in the sheet

## Sheet Structure

| Column | Description |
|--------|-------------|
| Title | Extracted content title/keyword |
| Category | Content type/category |
| Tags | Keywords/tags |
| Content | Full extracted text |
| Source | Book/document name |
| Author | Author name |
| Date Added | Extraction date |
| Unique ID | Hash for deduplication |
| Notes | Your comments |

## Discord Thread Setup

### Thread 1: Extraction Workflow
- Task started alerts
- Progress updates
- Completion notifications
- Review reminders

### Thread 2: Token Safety
- Usage estimations
- Budget warnings
- Approval requests
- Stop alerts

## License

MIT
