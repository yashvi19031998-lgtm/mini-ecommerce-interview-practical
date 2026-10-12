@echo off
cd /d "E:\MyWork\mini-ecommerce-interview-practical\test-demo"
echo ====================================================== >> scraper_log.txt
echo [%date% %time%] Scheduled scraper run started >> scraper_log.txt
"C:\Users\Admin\AppData\Local\Python\pythoncore-3.14-64\python.exe" scraper.py >> scraper_log.txt 2>&1
echo [%date% %time%] Scheduled scraper run completed >> scraper_log.txt
