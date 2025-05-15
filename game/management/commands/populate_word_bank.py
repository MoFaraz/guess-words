from django.core.management.base import BaseCommand
from game.models import WordBank


class Command(BaseCommand):
    help = 'Populates the word pool with words for different difficulty levels'

    def handle(self, *args, **options):
        # Clear existing words
        WordBank.objects.all().delete()

        # Easy words (4-5 letters)
        easy_words = [
            'game', 'play', 'word', 'time', 'code', 'work', 'turn',
            'card', 'home', 'book', 'door', 'wind', 'cold', 'warm',
            'rain', 'snow', 'tree', 'sing', 'fish', 'bird', 'cake',
            'lake', 'city', 'moon', 'star', 'ship', 'road', 'path'
        ]

        # Medium words (6-7 letters)
        medium_words = [
            'python', 'coding', 'player', 'system', 'dinner', 'coffee',
            'rainbow', 'summer', 'winter', 'garden', 'window', 'castle',
            'melody', 'rhythm', 'autumn', 'basket', 'camera', 'pencil',
            'kitchen', 'laptop', 'concert', 'journey', 'picture', 'theater'
        ]

        # Hard words (8+ letters)
        hard_words = [
            'developer', 'algorithm', 'interface', 'challenge', 'different',
            'experience', 'community', 'beautiful', 'adventure', 'knowledge',
            'discovery', 'chocolate', 'friendship', 'playground', 'education',
            'technology', 'collection', 'revolution', 'generation', 'innovation'
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
