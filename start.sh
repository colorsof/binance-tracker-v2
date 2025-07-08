#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Binance Tracker V2${NC}"
echo "=================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -q -r requirements.txt

# Create data directory if it doesn't exist
mkdir -p data

# Kill any existing processes on port 5000
echo "Checking for existing processes..."
python3 main.py --kill 2>/dev/null

# Start the tracker
echo -e "\n${GREEN}Starting tracker...${NC}"
echo "Access the web interface at: http://127.0.0.1:5000"
echo -e "Press ${RED}Ctrl+C${NC} to stop\n"

# Run the tracker
python3 main.py