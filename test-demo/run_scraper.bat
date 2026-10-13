@echo off
cd /d "%~dp0"
echo ====================================================== >> scraper_log.txt
echo [%date% %time%] Scheduled scraper run started >> scraper_log.txt
python scraper.py >> scraper_log.txt 2>&1
echo [%date% %time%] Scheduled scraper run completed >> scraper_log.txt
