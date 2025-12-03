import os
import re
import sys
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
from icalendar import Calendar
from tabulate import tabulate


def load_ical_url():
    """Load ICAL URL from .env file"""
    load_dotenv()
    ical_url = os.getenv('ICAL')
    if not ical_url:
        print("Error: ICAL environment variable not found in .env file")
        sys.exit(1)
    return ical_url


def fetch_ics_file(url):
    """Fetch ICS file from URL"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ICS file: {e}")
        sys.exit(1)


def parse_ics_content(ics_content):
    """Parse ICS content and return calendar object"""
    try:
        return Calendar.from_ical(ics_content)
    except Exception as e:
        print(f"Error parsing ICS file: {e}")
        sys.exit(1)


def extract_code_from_description(description):
    """Extract code and display name from the fifth line of description (format: CODE123 - Display Name)"""
    if not description:
        return None, None
    
    lines = description.split('\n')
    if len(lines) < 5:
        return None, None
    
    try:
        fifth_line = next(l for l in lines[4:] if 1 <= l.count("-") <= 2).strip()
    except StopIteration:
        return None, None
    # Match pattern: capital letters and digits followed by " - " and the display name
    match = re.match(r'^([A-Z0-9]+)\s*-\s*(.+)$', fifth_line)
    if match:
        return match.group(1), match.group(2).strip()
    return None, None


def extract_category_from_title(title):
    """Extract category (TP/TD/CM) from event title"""
    if not title:
        return None, False
    
    categories = []
    if 'TP' in title:
        categories.append('TP')
    if 'TD' in title:
        categories.append('TD')
    if 'CM' in title:
        categories.append('CM')
    
    if len(categories) == 0:
        return None, False
    elif len(categories) == 1:
        return categories[0], False
    else:
        return None, True  # Multiple categories found - error


def calculate_duration_hours(event):
    """Calculate event duration in hours"""
    dtstart = event.get('DTSTART')
    dtend = event.get('DTEND')
    
    if not dtstart or not dtend:
        return 0
    
    start = dtstart.dt
    end = dtend.dt
    
    # Handle both datetime and date objects
    if hasattr(start, 'hour'):
        duration = end - start
        return duration.total_seconds() / 3600
    else:
        # All-day events
        return 24


def format_number(value):
    """Format number without trailing zeros"""
    # Format with up to 2 decimals, remove trailing zeros
    return f"{value:.2f}".rstrip('0').rstrip('.')


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Calculate teaching hours from ICS calendar')
    parser.add_argument('--done', action='store_true', 
                        help='Only include events that have already occurred (in the past)')
    args = parser.parse_args()
    
    print("Loading ICS calendar and calculating hours...\n")
    
    # Load ICAL URL from .env
    ical_url = load_ical_url()
    print(f"Fetching calendar from: {ical_url}")
    
    # Fetch and parse ICS file
    ics_content = fetch_ics_file(ical_url)
    calendar = parse_ics_content(ics_content)
    
    # Get current time for filtering
    now = datetime.now()
    if args.done:
        print(f"Filtering to show only past events (before {now.strftime('%Y-%m-%d %H:%M')})\n")
    
    # Data structure: {code: {category: hours}}
    hours_by_code = defaultdict(lambda: {'TP': 0, 'TD': 0, 'CM': 0})
    code_names = {}  # Store display names for each code
    errors = []
    
    # Process events
    event_count = 0
    skipped_future = 0
    for component in calendar.walk():
        if component.name == "VEVENT":
            # Check if we should filter by date
            if args.done:
                dtend = component.get('DTEND')
                if dtend:
                    end_time = dtend.dt
                    # Convert to datetime if it's a date object
                    if not hasattr(end_time, 'hour'):
                        # For all-day events, consider them past if the date has passed
                        end_time = datetime.combine(end_time, datetime.max.time())
                    # Make naive datetime timezone-aware comparison safe
                    if hasattr(end_time, 'tzinfo') and end_time.tzinfo is not None:
                        # If end_time is timezone-aware, make now timezone-aware too
                        from datetime import timezone
                        now_compare = now.replace(tzinfo=timezone.utc).astimezone(end_time.tzinfo)
                    else:
                        now_compare = now
                    
                    # Skip future events
                    if end_time > now_compare:
                        skipped_future += 1
                        continue
            
            event_count += 1
            
            # Get event details
            title = str(component.get('SUMMARY', ''))
            description = str(component.get('DESCRIPTION', ''))
            
            # Extract code from description
            code, display_name = extract_code_from_description(description)
            if not code:
                errors.append(f"Warning: Could not extract code from event: {title}")
                continue
            
            # Store the display name
            if code not in code_names and display_name:
                code_names[code] = display_name
            
            # Extract category from title
            category, multiple_found = extract_category_from_title(title)
            if multiple_found:
                errors.append(f"ERROR: Multiple categories (TP/TD/CM) found in event: {title}")
                continue
            if not category:
                errors.append(f"Warning: No category (TP/TD/CM) found in event: {title}")
                continue
            
            # Calculate duration
            duration = calculate_duration_hours(component)
            
            # Add to totals
            hours_by_code[code][category] += duration
    
    print(f"\nProcessed {event_count} events")
    if args.done and skipped_future > 0:
        print(f"Skipped {skipped_future} future events")
    print()
    
    # Display errors
    if errors:
        print("=" * 80)
        print("WARNINGS AND ERRORS:")
        print("=" * 80)
        for error in errors:
            print(error)
        print()
    
    # Calculate and display results
    print("HOURS SUMMARY BY CODE")
    print()
    
    # HETD conversion rates
    HETD_RATES = {'TP': 2/3, 'TD': 1, 'CM': 1.5}
    
    # Prepare table data
    table_data = []
    grand_total_cm = 0
    grand_total_td = 0
    grand_total_tp = 0
    grand_total_hours = 0
    grand_total_hetd = 0
    
    # Build table rows
    for code in sorted(hours_by_code.keys()):
        display_name = code_names.get(code, "Unknown")
        code_display = f"{code} - {display_name}"
        
        cm_hours = hours_by_code[code]['CM']
        td_hours = hours_by_code[code]['TD']
        tp_hours = hours_by_code[code]['TP']
        
        total_hours = cm_hours + td_hours + tp_hours
        total_hetd = (cm_hours * HETD_RATES['CM'] + 
                      td_hours * HETD_RATES['TD'] + 
                      tp_hours * HETD_RATES['TP'])
        
        # Update grand totals
        grand_total_cm += cm_hours
        grand_total_td += td_hours
        grand_total_tp += tp_hours
        grand_total_hours += total_hours
        grand_total_hetd += total_hetd
        
        # Add row to table
        table_data.append([
            code_display,
            format_number(cm_hours),
            format_number(td_hours),
            format_number(tp_hours),
            format_number(total_hours),
            format_number(total_hetd)
        ])
    
    # Add separator line before total
    from tabulate import SEPARATING_LINE
    table_data.append(SEPARATING_LINE)
    
    # Add total row
    table_data.append([
        "TOTAL",
        format_number(grand_total_cm),
        format_number(grand_total_td),
        format_number(grand_total_tp),
        format_number(grand_total_hours),
        format_number(grand_total_hetd)
    ])
    
    # Print table using tabulate
    headers = ["Code & Name", "CM", "TD", "TP", "Total hours", "Total HETD"]
    print(tabulate(table_data, headers=headers, tablefmt="simple", numalign="right"))


if __name__ == "__main__":
    main()
