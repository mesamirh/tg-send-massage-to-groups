from pyrogram import Client
from datetime import datetime, timedelta
import asyncio
import json
import os
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables
load_dotenv()

class TelegramManager:
    def __init__(self):
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.sessions_file = 'sessions.json'
        self.clients = []
        self.sessions_data = self.load_sessions()

    def load_sessions(self) -> Dict:
        """Load saved sessions data from JSON file"""
        try:
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"accounts": [], "targets": []}

    def save_sessions(self):
        """Save sessions data to JSON file"""
        with open(self.sessions_file, 'w') as f:
            json.dump(self.sessions_data, f, indent=4)

    def detect_existing_sessions(self):
        """Detect all .session files in the current directory and subdirectories"""
        session_files = []
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sessions_dir = os.path.join(current_dir, "sessions")
        print(f"Searching for sessions in: {current_dir} and {sessions_dir}")
        
        # Search in both main directory and sessions folder
        search_dirs = [current_dir]
        if os.path.exists(sessions_dir):
            search_dirs.append(sessions_dir)
        
        for search_dir in search_dirs:
            for root, dirs, files in os.walk(search_dir):
                for file in files:
                    if file.endswith('.session'):
                        session_name = file.replace('.session', '')
                        # Skip temp_session
                        if session_name == 'temp_session':
                            continue
                        if session_name not in [acc['session_name'] for acc in self.sessions_data['accounts']]:
                            self.sessions_data['accounts'].append({
                                "session_name": session_name
                            })
                            session_files.append(session_name)
        
        if session_files:
            print(f"Found existing sessions: {', '.join(session_files)}")
            self.save_sessions()
        else:
            print("No existing session files found")
        return session_files

    async def add_new_account(self):
        """Interactive account addition"""
        # Create client with temporary session name
        client = Client(
            "temp_session",
            api_id=self.api_id,
            api_hash=self.api_hash
        )
        
        try:
            await client.start()
            me = await client.get_me()
            
            # Use username if available, otherwise use first_name
            session_name = me.username or me.first_name
            # Ensure session name is valid for file system
            session_name = "".join(c for c in session_name if c.isalnum() or c in ('-', '_'))
            
            # Stop the temporary client
            await client.stop()
            
            # Create new client with proper session name
            client = Client(
                session_name,
                api_id=self.api_id,
                api_hash=self.api_hash
            )
            await client.start()
            
            print(f"Successfully logged in as {me.first_name}")
            
            # Save account info
            if session_name not in [acc['session_name'] for acc in self.sessions_data['accounts']]:
                self.sessions_data['accounts'].append({
                    "session_name": session_name
                })
                self.save_sessions()
            
            self.clients.append(client)
            return client
            
        except Exception as e:
            print(f"Failed to initialize client: {str(e)}")
            return None

    async def add_target(self):
        """Interactive target addition"""
        target = input("Enter target username/group/channel (with or without @) or link: ")
        message = input("Enter the message to send: ")
        
        # Clean up the target input
        if target.startswith('@'):
            target = target[1:]
        elif 't.me/' in target:
            target = target.split('t.me/')[-1]
        
        self.sessions_data['targets'].append({
            "recipient": target,
            "message": message
        })
        self.save_sessions()
        print(f"Added new target: {target}")

    async def send_message(self, client: Client, recipient: str, message: str):
        """Send message to specified recipient"""
        try:
            await client.send_message(recipient, message)
            print(f"Message sent successfully to {recipient}")
        except Exception as e:
            print(f"Failed to send message: {str(e)}")

    async def scheduled_message_sender(self):
        """Main loop for sending scheduled messages"""
        while True:
            # Send messages immediately
            for client in self.clients:
                for target in self.sessions_data['targets']:
                    try:
                        print(f"\nSending message to {target['recipient']}...")
                        await self.send_message(
                            client,
                            target['recipient'],
                            target['message']
                        )
                    except Exception as e:
                        print(f"Error in scheduled sender: {str(e)}")
            
            next_time = datetime.now() + timedelta(hours=3)
            print(f"\nNext messages will be sent in 3 hours at {next_time.strftime('%H:%M:%S')}")
            # Wait for 3 hours before next round
            await asyncio.sleep(3 * 60 * 60)

    async def setup(self):
        """Initial setup and configuration"""
        print("\n" + "="*50)
        print("TG-SEND-MASSAGE-TO-GROUPS")
        print("="*50 + "\n")
        
        # Detect existing sessions
        self.detect_existing_sessions()
        
        # Initialize existing accounts
        for account in self.sessions_data['accounts']:
            try:
                # Check if session file is in sessions directory
                sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
                if os.path.exists(os.path.join(sessions_dir, f"{account['session_name']}.session")):
                    session_path = os.path.join("sessions", account['session_name'])
                else:
                    session_path = account['session_name']
                
                client = Client(
                    session_path,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    no_updates=True
                )
                
                # Skip temp_session as it's just temporary
                if account['session_name'] == 'temp_session':
                    continue
                    
                # Start the client without asking for phone number if already authorized
                await client.start()
                self.clients.append(client)
                print(f"Successfully loaded session: {account['session_name']}")
                    
            except Exception as e:
                print(f"Failed to load session {account['session_name']}: {str(e)}")
                # Remove failed session from accounts
                self.sessions_data['accounts'].remove(account)
                self.save_sessions()
        
        # Only ask to add new account if no existing accounts were successfully loaded
        if not self.clients:
            print("\nNo valid sessions found. Let's add a new account.")
            await self.add_new_account()
        else:
            while True:
                add_more = input("\nDo you want to add another account? (y/N): ").lower()
                if add_more != 'y':
                    break
                await self.add_new_account()
        
        # Add targets if none exist
        if not self.sessions_data['targets']:
            print("\nNo targets found. Let's add one.")
            await self.add_target()
        
        while True:
            add_more = input("\nDo you want to add another target? (y/N): ").lower()
            if add_more != 'y':
                break
            await self.add_target()

    async def run(self):
        """Main entry point to run the Telegram manager"""
        try:
            await self.setup()
            print("\nStarting scheduled message sender...")
            print("Press Ctrl+C to stop the program")
            print("="*50)
            await self.scheduled_message_sender()
        except KeyboardInterrupt:
            print("\nShutting down Telegram manager")
        finally:
            for client in self.clients:
                await client.stop()

if __name__ == "__main__":
    # Create and run the Telegram manager
    manager = TelegramManager()
    asyncio.run(manager.run())
