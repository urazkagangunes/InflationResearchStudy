import schedule
import time
from deneme import main

class DailyScraperScheduler:

    def __init__(self):

        schedule.every().day.at("12:00").do(self.run_job)

    def run_job(self):
        print("Scraper başlatılıyor...")
        main()
        print("Scraper tamamlandı.")

    def start(self):
        print("Zamanlayıcı çalışıyor...")
        while True:
            schedule.run_pending()
            time.sleep(30)


if __name__ == "__main__":
    scheduler = DailyScraperScheduler()
    scheduler.start()