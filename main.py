import os
import sys
import logging
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from markdownify import MarkdownConverter
import markdown

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    filename="/home/dcstang/mcp-trilium/debug.log",
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("--- SERVER STARTING ---")

class TriliumMarkdownConverter(MarkdownConverter):
    """Custom converter that preserves checkbox states as markdown task lists."""

    def convert_li(self, el, text=None, convert_as_inline=None, **kwargs):
        """Convert <li> elements, adding task list prefix if it contains a checkbox."""
        # Check if this list item contains a checkbox
        checkbox = el.find('input', type='checkbox')
        if checkbox:
            is_checked = checkbox.get('checked') is not None
            # Remove the checkbox from the text since we'll add it as prefix
            if text:
                text = text.strip()
            else:
                text = ''
            prefix = '- [x] ' if is_checked else '- [ ] '
            return prefix + text + '\n'
        # Call parent with all arguments
        if text is not None and convert_as_inline is not None:
            return super().convert_li(el, text, convert_as_inline, **kwargs)
        elif text is not None:
            return super().convert_li(el, text, **kwargs)
        else:
            return super().convert_li(el, **kwargs)

    def convert_input(self, el, text=None, convert_as_inline=None, **kwargs):
        """Convert <input type="checkbox"> - return empty string since we handle it in convert_li."""
        if el.get('type') == 'checkbox':
            # Return empty string - we handle the checkbox in convert_li
            return ''
        # Call parent with all arguments
        if text is not None and convert_as_inline is not None:
            return super().convert_input(el, text, convert_as_inline, **kwargs)
        elif text is not None:
            return super().convert_input(el, text, **kwargs)
        else:
            return super().convert_input(el, **kwargs)

def md(html):
    """Convert HTML to markdown, preserving checkbox states."""
    return TriliumMarkdownConverter().convert(html)

def html_from_markdown(md_text):
    """
    Convert Markdown to HTML for Trilium.
    Handles task lists with checkbox syntax.
    """
    # Configure markdown with extensions for better HTML output
    md_converter = markdown.Markdown(extensions=[
        'extra',           # Tables, fenced code, etc.
        'nl2br',          # Convert newlines to <br>
        'sane_lists',     # Better list handling
    ])
    
    # Convert markdown to HTML
    html = md_converter.convert(md_text)
    
    # Post-process: Convert markdown checkboxes to HTML checkboxes
    # - [ ] becomes <input type="checkbox">
    # - [x] becomes <input type="checkbox" checked>
    html = html.replace('[ ]', '<input type="checkbox">')
    html = html.replace('[x]', '<input type="checkbox" checked>')
    html = html.replace('[X]', '<input type="checkbox" checked>')
    
    return html


try:
    API_URL = "http://localhost:37840/etapi"
    API_KEY = os.environ.get("TRILIUM_API_KEY")

    if not API_KEY:
        logging.critical("NO API KEY FOUND IN ENVIRONMENT VARIABLES")

    HEADERS = {"Authorization": API_KEY, "Content-Type": "application/json"}

    mcp = FastMCP("Trilium")
except Exception as e:
    logging.critical(f"Initialization failed: {e}")
    sys.exit(1)

@mcp.tool()
def search_notes(query: str) -> str:
    logging.debug(f"Searching for: {query}")
    params = {"search": query, "fastSearch": "true", "limit": 10}
    try:
        url = f"{API_URL}/notes"
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        resp.raise_for_status()

        results = resp.json().get("results", [])
        logging.info(f"Found {len(results)} notes")
        return "\n".join([f"- {n['title']} (ID: {n['noteId']})" for n in results[:10]])
    except Exception as e:
        logging.error(f"Search failed: {e}")
        return f"Error: {e}"

@mcp.tool()
def read_note(note_id: str) -> str:
    logging.debug(f"Reading note: {note_id}")
    try:
        url = f"{API_URL}/notes/{note_id}/content"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        resp.raise_for_status()
        return md(resp.text)
    except Exception as e:
        logging.error(f"Read failed: {e}")
        return f"Error: {e}"

@mcp.tool()
def create_note(parent_id: str, title: str, content: str) -> str:
    """
    Create a new note.
    parent_id: The ID of the folder to put this note in.
    content: The body of the note in Markdown format.
    """
    logging.debug(f"Creating note '{title}' in '{parent_id}'")
    try:
        # Convert Markdown to HTML for Trilium
        content_html = html_from_markdown(content)
        
        data = {
            "parentNoteId": parent_id,
            "title": title,
            "type": "text",
            "content": content_html,
            "isExpanded": True
        }
        resp = requests.post(f"{API_URL}/create-note", json=data, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        note = resp.json()
        return f"Successfully created note '{note.get('title')}' (ID: {note.get('noteId')})"
    except Exception as e:
        logging.error(f"Create error: {e}")
        return f"Error creating note: {e}"

@mcp.tool()
def update_note(note_id: str, content: str) -> str:
    """
    Overwrites a note's content completely.
    content: The new body in Markdown format (use - [ ] for unchecked tasks, - [x] for checked).
    """
    logging.debug(f"Updating note: {note_id}")
    try:
        # Convert Markdown to HTML for Trilium
        content_html = html_from_markdown(content)
        
        # Update content using PUT to /notes/{noteId}/content
        content_headers = {
            "Authorization": API_KEY,
            "Content-Type": "text/plain; charset=utf-8"
        }
        resp = requests.put(
            f"{API_URL}/notes/{note_id}/content",
            data=content_html.encode('utf-8'),
            headers=content_headers,
            timeout=10
        )
        resp.raise_for_status()

        return f"Successfully updated note content (ID: {note_id})"
    except Exception as e:
        logging.error(f"Update error: {e}")
        return f"Error updating note: {e}"


@mcp.tool()
def update_note_title(note_id: str, title: str) -> str:
    """
    Update a note's title.
    note_id: The ID of the note to update.
    title: The new title for the note.
    """
    logging.debug(f"Updating note title: {note_id} to '{title}'")
    try:
        data = {"title": title}
        resp = requests.patch(
            f"{API_URL}/notes/{note_id}",
            json=data,
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        
        return f"Successfully updated note title to '{title}' (ID: {note_id})"
    except Exception as e:
        logging.error(f"Update title error: {e}")
        return f"Error updating note title: {e}"

@mcp.tool()
def set_note_dates(note_id: str, start_date: str, end_date: str = None) -> str:
    """
    Set start and end dates for a note to make it appear in calendar.
    note_id: The ID of the note to update.
    start_date: Start date in YYYY-MM-DD format (e.g., '2025-11-26').
    end_date: Optional end date in YYYY-MM-DD format. If not provided, uses start_date.
    """
    logging.debug(f"Setting dates for note: {note_id}")
    try:
        if end_date is None:
            end_date = start_date

        # Convert YYYY-MM-DD to DD/MM/YYYY format for Trilium
        from datetime import datetime
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        start_date_trilium = start_date_obj.strftime('%d/%m/%Y')

        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        end_date_trilium = end_date_obj.strftime('%d/%m/%Y')
        
        # First, get note details which includes attributes
        resp = requests.get(
            f"{API_URL}/notes/{note_id}",
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        note_data = resp.json()
        existing_attrs = note_data.get('attributes', [])
        
        # We need to set three attributes: dateNote, startDate, and endDate
        attrs_to_set = {
            'dateNote': start_date_trilium,  # DD/MM/YYYY format
            'startDate': start_date,          # YYYY-MM-DD format
            'endDate': end_date                # YYYY-MM-DD format
        }

        for attr_name, attr_value in attrs_to_set.items():
            # Check if this attribute already exists
            existing_attr = next((attr for attr in existing_attrs if attr['name'] == attr_name), None)

            if existing_attr:
                # Update existing attribute
                attr_id = existing_attr['attributeId']
                requests.patch(
                    f"{API_URL}/attributes/{attr_id}",
                    json={"value": attr_value},
                    headers=HEADERS,
                    timeout=10
                ).raise_for_status()
                logging.debug(f"Updated {attr_name} to {attr_value}")
            else:
                # Create new attribute
                requests.post(
                    f"{API_URL}/attributes",
                    json={
                        "noteId": note_id,
                        "type": "label",
                        "name": attr_name,
                        "value": attr_value
                    },
                    headers=HEADERS,
                    timeout=10
                ).raise_for_status()
                logging.debug(f"Created {attr_name} with value {attr_value}")

        return f"Successfully set dates for note (ID: {note_id}): dateNote={start_date_trilium}, startDate={start_date}, endDate={end_date}"
    except Exception as e:
        logging.error(f"Set dates error: {e}")
        return f"Error setting note dates: {e}"


if __name__ == "__main__":
    logging.info("Entering Event Loop")
    try:
        mcp.run()
    except Exception as e:
        logging.critical(f"Server Crashed: {e}")
