# Crypto News Scraper Setup Guide

This project is a web scraper designed to collect cryptocurrency news articles. Follow these instructions to set up your development environment.

## Conda Environment Setup

1. First, install Anaconda or Miniconda if you haven't already:
   - Download from [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)

2. Create a new conda environment:
```bash
conda create -n crypto_scraper python=3.10
```

3. Activate the environment:
```bash     
conda activate crypto_scraper
```
4. Install the required packages:
```bash
pip install -r requirements.txt
```

chrome driver setup. google chrome is preffered as the latest version is supported for twisted web scraping package


```bash

## Chrome Driver Setup

This project uses Selenium with Chrome for web scraping. Here's how to set it up:

### Option 1: Using undetected-chromedriver (Recommended)

This project uses `undetected-chromedriver` which helps bypass detection mechanisms. The package is already included in requirements.txt.

1. Make sure you have Google Chrome installed on your system
2. The driver will be automatically downloaded and configured when you run the scraper

### Option 2: Manual Chrome Driver Setup

If you prefer manual setup:

1. Check your Chrome version:
   - Open Chrome
   - Go to ⋮ (three dots) > Help > About Google Chrome
   - Note your Chrome version number

2. Download the matching ChromeDriver:
   - Visit [ChromeDriver Downloads](https://sites.google.com/chromium.org/driver/)
   - Download the version matching your Chrome browser
   - Extract the executable

3. Add ChromeDriver to your PATH:
   - **Windows**: 
     - Copy chromedriver.exe to `C:\Windows\System32` or
     - Add the chromedriver location to your System Environment Variables
   - **Linux/MacOS**:
     ```bash
     sudo mv chromedriver /usr/local/bin/
     sudo chmod +x /usr/local/bin/chromedriver
     ```

## Additional Setup 
```bash

Create a `.env` file in the project root:

Add any environment variables needed for the project
CHROME_DRIVER_PATH=/path/to/chromedriver # Optional if using undetected-chromedriver

Also can use google chrome[prefferred] as the latest version is supported 
/usr/bin/google-chrome
```