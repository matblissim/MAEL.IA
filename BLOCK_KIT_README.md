# Slack Block Kit - Morning Summary

## Overview

The morning summary now uses **Slack Block Kit** for a rich, interactive experience:

- ✅ **Better mobile rendering** (native Slack formatting)
- ✅ **Column layout** using `fields` (2 columns per section)
- ✅ **Interactive buttons** for drill-down and actions
- ✅ **Clean visual hierarchy** with headers, dividers, sections

## Features

### 1. Structured Layout

- **Header block**: Date in human-readable format ("Saturday 2nd November")
- **Section blocks**: Organized data with proper spacing
- **Divider blocks**: Clear visual separation
- **Context block**: Footer with metadata

### 2. Column Display

Each country shows data in a 2-column grid:
```
🇫🇷 1,234 acq.     |  📈 +15.2% YoY
Committed: 55%     |  Top: COUPON20
```

### 3. Interactive Buttons

#### Per-Country Details Button
- Click "Details" next to any country
- Opens **ephemeral message** (only visible to you) with:
  - Yesterday's full metrics
  - Cycle performance breakdown
  - NEW NEW / REACTIVATION mix

#### Global Actions
- **📊 View Full Analysis**: Posts detailed breakdown in thread
- **📥 Export Data**: CSV/Excel export (coming soon)

### 4. Button Actions

Defined in `morning_summary_handlers.py`:

| Action ID | Type | Behavior |
|-----------|------|----------|
| `view_country_details_{COUNTRY}` | Ephemeral | Country-specific details |
| `view_full_analysis` | Thread | Full analysis posted in thread |
| `export_data` | Ephemeral | Export options |

## Testing with Block Kit Builder

### 1. Access Block Kit Builder
Go to: https://app.slack.com/block-kit-builder

### 2. Load Example
Copy contents of `block_kit_example.json` and paste into Block Kit Builder

### 3. Preview
- **Desktop view**: See full layout
- **Mobile view**: Toggle to see mobile rendering (top-right)

### 4. Modify
- Edit text, add fields, change colors
- Test different button configurations
- See live preview

## Implementation

### Generate Blocks

```python
from morning_summary import generate_daily_summary_blocks

result = generate_daily_summary_blocks()
blocks = result['blocks']
fallback_text = result['text']
```

### Send to Slack

```python
from morning_summary import send_morning_summary

# Send with Block Kit (default)
send_morning_summary(channel="bot-lab", use_blocks=True)

# Send plain text (fallback)
send_morning_summary(channel="bot-lab", use_blocks=False)
```

### Manual Trigger

```
@Franck morning
```

## Block Kit Capabilities

### What You CAN Do

✅ **Fields**: 2-column layout automatically
✅ **Buttons**: Interactive actions
✅ **Modals**: Pop-up dialogs (not implemented yet)
✅ **Select menus**: Dropdowns (not implemented yet)
✅ **Rich text**: Bold, italic, links, code
✅ **Emojis**: Full emoji support
✅ **Context**: Small metadata text
✅ **Image blocks**: Display images

### What You CANNOT Do

❌ **True tables**: No native table block (use fields for 2 columns)
❌ **3+ columns**: Limited to 2 columns via fields
❌ **Custom CSS**: No styling beyond Slack's defaults
❌ **Complex charts**: Use image blocks with chart URLs

## Workarounds for Tables

Since Slack doesn't support true tables, we use:

1. **Fields** (2 columns):
```json
{
  "type": "section",
  "fields": [
    {"type": "mrkdwn", "text": "Column 1"},
    {"type": "mrkdwn", "text": "Column 2"}
  ]
}
```

2. **Monospace text** with code blocks:
```
`FR │ 1,234 │ +15%`
`DE │   876 │  -8%`
```

3. **Bullet points** (current approach):
More mobile-friendly than fake tables

## Configuration

Enable/disable Block Kit in `.env`:

```bash
# Use Block Kit format (default: true)
MORNING_SUMMARY_USE_BLOCKS=true
```

## File Structure

```
morning_summary.py              # Core logic + blocks generator
morning_summary_handlers.py     # Interactive button handlers
block_kit_example.json          # Example for Block Kit Builder
app.py                          # Registers handlers
```

## Next Steps

Potential enhancements:

1. **Modals**: Click "Details" → open modal with charts
2. **Select menus**: Filter by country/metric
3. **Update messages**: Real-time updates as data changes
4. **Charts**: Integrate Chart.js/QuickChart for visual graphs
5. **Drill-down**: Click country → open thread with hourly breakdown
6. **CSV export**: Implement actual export functionality

## Resources

- [Block Kit Builder](https://app.slack.com/block-kit-builder)
- [Block Kit Documentation](https://api.slack.com/block-kit)
- [Interactive Components](https://api.slack.com/interactivity)
- [Block Kit Examples](https://api.slack.com/block-kit/building)
