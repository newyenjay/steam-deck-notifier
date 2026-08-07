# refurbished steam deck notifier - notifies when refurbished steam deck is in stock
#  Copyright (C) <2025>  <Oliver Blass>
# 
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from time import gmtime, strftime
import requests
import os
import csv
from datetime import datetime
import argparse
import json
import smtplib
from email.message import EmailMessage


# Default values
DEFAULT_COUNTRY_CODE = 'CA'
DEFAULT_WEBHOOK_URL = "https://discord.com/api/webhooks/some_webhook"

class SteamDeckModel:
    def __init__(self, version: str, package_id: str, is_oled: bool, is_new: bool = False):
        self.version = version
        self.package_id = package_id
        self.is_oled = is_oled
        self.is_new = is_new

def get_daily_csv_path(csv_dir: str, country_code: str) -> str:
    """Generate the CSV file path for today's date and country"""
    if not csv_dir:
        return ""
    
    # Create directory if it doesn't exist
    os.makedirs(csv_dir, exist_ok=True)
    
    # Generate filename with today's date and country code
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{country_code}_{today}.csv"
    return os.path.join(csv_dir, filename)

def initialize_logs(csv_dir: str, country_code: str):
    """Initialize CSV log file if it doesn't exist"""
    if not csv_dir:
        return
        
    log_file = get_daily_csv_path(csv_dir, country_code)
    if not os.path.exists(log_file):
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['unix_timestamp', 'storage_gb', 
                        'display_type', 'package_id', 'available'])

def log_availability_data(version, package_id, available, is_oled, csv_dir: str, country_code: str):
    """Log availability data in CSV format"""
    if not csv_dir:
        return
        
    log_file = get_daily_csv_path(csv_dir, country_code)
    timestamp = datetime.now()
    unix_timestamp = int(timestamp.timestamp())
    display_type = "OLED" if is_oled else "LCD"
    
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([unix_timestamp, version, display_type, package_id, available])

def send_email_notification(subject: str, body: str, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str, smtp_from: str, smtp_to: str, smtp_use_tls: bool = True):
    """Send a notification email using SMTP."""
    if not smtp_host or not smtp_to:
        print("Email notification skipped: SMTP host or recipient is not configured")
        return

    recipients = [address.strip() for address in smtp_to.split(',') if address.strip()]
    if not recipients:
        print("Email notification skipped: no valid recipients configured")
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from or smtp_user or "steam-deck-notifier@localhost"
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port or 587) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(message, to_addrs=recipients)
        print(f"Email sent to {', '.join(recipients)}")
    except Exception as e:
        print(f"Failed to send email notification: {e}")


def superduperscraper(model: SteamDeckModel, csv_dir: str, country_code: str, smtp_config: dict, role_ids: dict = None):
    # Build Steam API URL with country code
    url = f'https://api.steampowered.com/IPhysicalGoodsService/CheckInventoryAvailableByPackage/v1?origin=https:%2F%2Fstore.steampowered.com&country_code={country_code}&packageid='

    oldvalue = ""
    # Get previous availability from file
    if os.path.isfile(f"{model.package_id}_{country_code}.txt"):
        with open(f"{model.package_id}_{country_code}.txt", "r") as file_read:
            oldvalue = file_read.read()
    
    print("Previous value: " + oldvalue)

    try:
        # Make request to Steam API
        response = requests.get(url+model.package_id, timeout=10)
        response.raise_for_status()
        
        # Get availability status
        availability = str(response.json()["response"]["inventory_available"])
        current_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        
        print(f"{current_time} >> {model.version}GB {'OLED' if model.is_oled else 'LCD'} Result: {availability}")
        
        # Save new availability to file
        with open(f"{model.package_id}_{country_code}.txt", "w") as file:
            file.write(availability)
        
        # Check if status changed
        status_changed = oldvalue != availability and oldvalue != ""
        
        # Log data
        log_availability_data(model.version, model.package_id, availability == "True", model.is_oled, csv_dir, country_code)
        
        # Send email notification only on status change
        if status_changed:
            display_type = "OLED" if model.is_oled else "LCD"
            condition_type = "new" if model.is_new else "refurbished"
            availability_text = "available" if availability == "True" else "not available"
            subject = f"{condition_type.title()} Steam Deck {model.version}GB {display_type} is {availability_text}"
            body = f"{condition_type.title()} Steam Deck {model.version}GB {display_type} is now {availability_text}."
            send_email_notification(
                subject=subject,
                body=body,
                smtp_host=smtp_config.get("host", ""),
                smtp_port=int(smtp_config.get("port", 587) or 587),
                smtp_user=smtp_config.get("user", ""),
                smtp_password=smtp_config.get("password", ""),
                smtp_from=smtp_config.get("from", ""),
                smtp_to=smtp_config.get("to", ""),
                smtp_use_tls=bool(smtp_config.get("use_tls", True)),
            )
            
    except requests.RequestException as e:
        print(f"Error fetching data for {model.version}GB: {e}")
        log_availability_data(model.version, model.package_id, False, model.is_oled, csv_dir, country_code)
    except Exception as e:
        print(f"Unexpected error for {model.version}GB: {e}")

def load_role_mapping(role_file: str) -> dict:
    """Load role mapping from JSON file"""
    if not role_file or not os.path.exists(role_file):
        return {}
    
    try:
        with open(role_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load role mapping from {role_file}: {e}")
        return {}


def load_dotenv(dotenv_path: str = None) -> dict:
    """Load environment variables from a .env file if it exists."""
    if not dotenv_path:
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.exists(dotenv_path):
        return {}

    loaded_values = {}
    with open(dotenv_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded_values[key] = value

    return loaded_values


def main():
    """Main function to check all Steam Deck models"""
    load_dotenv()

    parser = argparse.ArgumentParser(description='Check Steam Deck availability and optionally log to CSV')
    parser.add_argument('--include-new-models', action='store_true', help='Include request for new steam decks (not just refurbs)')
    parser.add_argument('--csv-dir', help='Directory path for daily CSV log files')
    parser.add_argument('--country-code', default=DEFAULT_COUNTRY_CODE, 
                       help=f'Country code for Steam API (default: {DEFAULT_COUNTRY_CODE})')
    parser.add_argument('--smtp-host', help='SMTP server host for email notifications')
    parser.add_argument('--smtp-port', type=int, default=None, help='SMTP server port (default: 587)')
    parser.add_argument('--smtp-user', help='SMTP username')
    parser.add_argument('--smtp-password', help='SMTP password')
    parser.add_argument('--smtp-from', help='Sender email address')
    parser.add_argument('--smtp-to', help='Recipient email address')
    parser.add_argument('--smtp-use-tls', action='store_true', help='Enable TLS for SMTP connections')
    parser.add_argument('--role-mapping', help='JSON file containing package_id to role_id mapping')
    parser.add_argument('--csv-log', help='Deprecated: This option is no longer supported (last supported version v2.0.0).')
    
    args = parser.parse_args()

    if args.csv_log:
        print("w: Deprecated: This option is no longer supported (last supported version v2.0.0).")
    
    csv_dir = args.csv_dir if args.csv_dir else ""
    initialize_logs(csv_dir, args.country_code)
    
    # Load role mapping
    role_ids = load_role_mapping(args.role_mapping)
    
    if csv_dir:
        today_file = get_daily_csv_path(csv_dir, args.country_code)
        print(f"Logging enabled to: {today_file}")
    else:
        print("Logging disabled")
    
    print(f"Country code: {args.country_code}")
    smtp_config = {
        "host": args.smtp_host or os.getenv("SMTP_HOST", ""),
        "port": args.smtp_port if args.smtp_port is not None else int(os.getenv("SMTP_PORT", "587")),
        "user": args.smtp_user or os.getenv("SMTP_USER") or os.getenv("EMAIL_ADDRESS", ""),
        "password": args.smtp_password or os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD", ""),
        "from": args.smtp_from or os.getenv("SMTP_FROM") or os.getenv("EMAIL_FROM", ""),
        "to": args.smtp_to or os.getenv("SMTP_TO") or os.getenv("EMAIL_TO", ""),
        "use_tls": args.smtp_use_tls or os.getenv("SMTP_USE_TLS", "true").lower() == "true",
    }
    if smtp_config["to"]:
        print(f"Email notifications enabled for: {smtp_config['to']}")
    else:
        print("Email notifications disabled")
    
    # Steam Deck models
    refurbModels = [
        #REFURBISHED
        SteamDeckModel("64", "903905", False),    # 64gb lcd
        SteamDeckModel("256", "903906", False),   # 256gb lcd  
        SteamDeckModel("512", "903907", False),   # 512gb lcd
        SteamDeckModel("512", "1202542", True),   # 512gb oled
        SteamDeckModel("1024", "1202547", True),  # 1tb oled
    ]   

    newModels = [
        #NEW
        SteamDeckModel("512", "946113", True, is_new=True),    # 512gb oled
        SteamDeckModel("1024", "946114", True, is_new=True),   # 1tb oled
        # Optional: Phasing out LCD models
        SteamDeckModel("256", "595604", False, is_new=True),   # 256gb lcd

        #64gb and 512gb lcd aren't being sold as new anymore
        #SteamDeckModel("64", "595603", False, is_new=True),    # 64gb lcd
        #SteamDeckModel("512", "595605", False, is_new=True),   # 512gb lcd
    ]

    if args.include_new_models:
        models = refurbModels + newModels
    else:
        models = refurbModels

    if role_ids:
        print(f"Role mapping loaded: {len(role_ids)} entries")
        if not len(role_ids) == len(models):
            print("Warning..............Role mapping doesn't match models. Pinging roles won't work as expected.")
    else:
        print("No role mapping - notifications will not ping roles")
    
    for model in models:
        superduperscraper(model, csv_dir, args.country_code, smtp_config, role_ids)

if __name__ == "__main__":
    main()