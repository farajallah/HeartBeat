#!/usr/bin/env python3
"""
Local Heartbeat Agent

This script sends heartbeat requests to the attendance tracker server every minute.
It should be run via OS scheduler (cron, Task Scheduler, etc.) rather than as a daemon.

Usage:
    python heartbeat.py

Environment variables:
    SERVER_URL: Base URL of the attendance server (default: http://localhost:8000)
    BEARER_TOKEN: Authentication token (required)
    DEVICE_ID: Unique device identifier (default: hostname)
    TIMEZONE: Timezone for the device (default: UTC)
"""

import os
import sys
import time
import json
import logging
import platform
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file first, then system environment
load_dotenv()

# Configuration
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:8000')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')  # Use BEARER_TOKEN to match .env file
DEVICE_ID = os.getenv('DEVICE_ID', platform.node().split('.')[0])
TIMEZONE = os.getenv('TIMEZONE', 'UTC')
HEARTBEAT_ENDPOINT = f"{SERVER_URL}/api/heartbeat"
TIMEOUT = 10  # seconds

# Setup logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.heartbeat_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class HeartbeatAgent:
    def __init__(self):
        self.server_url = SERVER_URL
        self.bearer_token = BEARER_TOKEN
        self.device_id = DEVICE_ID
        self.timezone = TIMEZONE
        self.endpoint = HEARTBEAT_ENDPOINT
        
        # Validate configuration
        if not self.bearer_token:
            logger.error("BEARER_TOKEN environment variable is required")
            sys.exit(1)
        
        logger.info(f"Heartbeat agent initialized")
        logger.info(f"Device ID: {self.device_id}")
        logger.info(f"Server: {self.server_url}")
        logger.info(f"Timezone: {self.timezone}")

    def send_heartbeat(self) -> bool:
        """Send a single heartbeat to the server"""
        headers = {
            'Authorization': f'Bearer {self.bearer_token}',
            'Content-Type': 'application/json',
            'User-Agent': f'HeartbeatAgent/{self.device_id}'
        }
        
        payload = {
            'device_id': self.device_id,
            'timezone': self.timezone
        }
        
        try:
            logger.debug(f"Sending heartbeat to {self.endpoint}")
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                logger.debug("Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"Server returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.warning("Request timed out")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error - server may be offline")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def run_once(self) -> int:
        """Run the agent once and return exit code"""
        logger.info("Sending heartbeat...")
        
        success = self.send_heartbeat()
        
        if success:
            logger.info("Heartbeat sent successfully")
            return 0
        else:
            logger.error("Failed to send heartbeat")
            return 1

    def test_connection(self) -> bool:
        """Test connection to server"""
        try:
            response = requests.get(f"{self.server_url}/", timeout=5)
            return response.status_code in [200, 302]  # 302 for redirect to dashboard
        except Exception:
            return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Heartbeat agent for time attendance tracker')
    parser.add_argument('--test', action='store_true', help='Test connection to server')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--device-id', help='Override device ID')
    args = parser.parse_args()
    
    # Override device ID if provided
    if args.device_id:
        global DEVICE_ID
        DEVICE_ID = args.device_id
    
    agent = HeartbeatAgent()
    
    if args.test:
        logger.info("Testing connection to server...")
        if agent.test_connection():
            logger.info("Connection successful")
            sys.exit(0)
        else:
            logger.error("Connection failed")
            sys.exit(1)
    
    if args.once:
        sys.exit(agent.run_once())
    
    # Default behavior: send one heartbeat
    sys.exit(agent.run_once())


if __name__ == "__main__":
    main()
