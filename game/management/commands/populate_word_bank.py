from django.core.management.base import BaseCommand
from game.models import WordBank


class Command(BaseCommand):
    help = 'Populates the word pool with words for different difficulty levels'

    def handle(self, *args, **options):
        WordBank.objects.all().delete()

        easy_words = [
            'باران', 'دریا', 'خورشید', 'کتاب', 'درخت', 'ماهی', 'خانه',
            'مدرسه', 'دوست', 'ماشین', 'گربه', 'پرنده', 'قلم', 'دست',
            'گل', 'کوه', 'باد', 'آب', 'آتش', 'چشم'
        ]

        medium_words = [
            'دانشجو', 'پاییز', 'سیب‌زمینی', 'فرودگاه', 'پروانه',
            'نویسنده', 'دستگاه', 'کلاسیک', 'فرهنگ', 'بازیگر',
            'ترانه', 'کامپیوتر', 'کتابخانه', 'میدان', 'تاریخچه'
        ]

        hard_words = [
            'دانشگاه', 'برنامه‌نویس', 'کارآفرینی', 'الگوریتم',
            'کاربرپسند', 'مسئولیت', 'روان‌شناسی', 'پیشرفت',
            'آموزشگاه', 'هوشمندسازی', 'دستاورد', 'همکاری',
            'توسعه‌دهنده', 'سیستم‌عامل', 'زیبایی‌شناسی'
        ]

        # Add words to the database
        for word in easy_words:
            WordBank.objects.create(word=word, difficulty=1)

        for word in medium_words:
            WordBank.objects.create(word=word, difficulty=2)

        for word in hard_words:
            WordBank.objects.create(word=word, difficulty=3)

        self.stdout.write(self.style.SUCCESS(
            f'Successfully added {len(easy_words)} easy words, {len(medium_words)} medium words, and {len(hard_words)} hard words to the pool'))
