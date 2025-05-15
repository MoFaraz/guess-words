from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from unittest.mock import patch
from datetime import timedelta

from game.models import Game, Player, GuessHistory, WordBank
from game.serializers import GameListSerializer, GameDetailSerializer

User = get_user_model()


class GameViewSetTests(APITestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(username='testuser1', password='password123')
        self.user2 = User.objects.create_user(username='testuser2', password='password123')
        self.admin = User.objects.create_superuser(username='admin', password='admin123')

        # Create test word
        self.test_word = WordBank.objects.create(word='python', category='programming')

        # Create API client
        self.client = APIClient()

        # Create a test game
        self.client.force_authenticate(user=self.user1)
        response = self.client.post('/api/games/', {'word_length': 6, 'max_attempts': 6})
        self.game_id = response.data['id']

        # Create another game with different status for filtering tests
        self.completed_game = Game.objects.create(
            creator=self.user1,
            word='hello',
            status=3,  # Completed
            max_attempts=6,
            attempts_left=0
        )

    def test_list_games(self):
        response = self.client.get('/api/games/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Two games created in setup

    def test_filter_games_by_status(self):
        response = self.client.get('/api/games/', {'status': 1})  # Waiting status
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        response = self.client.get('/api/games/', {'status': 3})  # Completed status
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_game(self):
        response = self.client.get(f'/api/games/{self.game_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.game_id)

    def test_join_game(self):
        # Switch to user2
        self.client.force_authenticate(user=self.user2)

        response = self.client.post(f'/api/games/{self.game_id}/join/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that player was added to the game
        game = Game.objects.get(id=self.game_id)
        self.assertEqual(game.players.count(), 1)
        self.assertEqual(game.players.first().user, self.user2)

    def test_join_game_already_joined(self):
        # Have user2 join the game
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/games/{self.game_id}/join/')

        # Try to join again
        response = self.client.post(f'/api/games/{self.game_id}/join/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already in this game', response.data['error'])

    def test_join_game_invalid_status(self):
        # Try to join a completed game
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f'/api/games/{self.completed_game.id}/join/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not in waiting status', response.data['error'])

    def test_start_game(self):
        # Have user2 join the game
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/games/{self.game_id}/join/')

        # Switch back to creator to start game
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/games/{self.game_id}/start/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that game status changed
        game = Game.objects.get(id=self.game_id)
        self.assertEqual(game.status, 2)  # Active status

    def test_start_game_not_creator(self):
        # Have user2 join the game
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/games/{self.game_id}/join/')

        # Try to start the game as non-creator
        response = self.client.post(f'/api/games/{self.game_id}/start/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only game creator', response.data['error'])

    def test_start_game_insufficient_players(self):
        # Try to start without enough players
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(f'/api/games/{self.game_id}/start/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least 2 players', response.data['error'])

    @patch('api.models.Game.guess_letter')
    def test_guess_letter(self, mock_guess_letter):
        # Set up the mock to return a successful guess
        mock_guess_letter.return_value = {
            'success': True,
            'message': 'Letter found in word!',
            'points': 10
        }

        # Start game with two players
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/games/{self.game_id}/join/')

        self.client.force_authenticate(user=self.user1)
        self.client.post(f'/api/games/{self.game_id}/start/')

        # Make a guess
        response = self.client.post(
            f'/api/games/{self.game_id}/guess/',
            {'letter': 'p'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['points'], 10)
        self.assertEqual(response.data['result'], 'Letter found in word!')

        # Check that guess history was created
        history = GuessHistory.objects.filter(game_id=self.game_id)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().letter, 'p')

    @patch('api.models.Game.guess_letter')
    def test_guess_letter_error(self, mock_guess_letter):
        # Set up the mock to return an error
        mock_guess_letter.return_value = {
            'success': False,
            'message': 'Not your turn'
        }

        # Start game with two players
        self.client.force_authenticate(user=self.user2)
        self.client.post(f'/api/games/{self.game_id}/join/')

        self.client.force_authenticate(user=self.user1)
        self.client.post(f'/api/games/{self.game_id}/start/')

        # Make a guess
        response = self.client.post(
            f'/api/games/{self.game_id}/guess/',
            {'letter': 'p'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Not your turn')

    def test_get_history(self):
        # Create some guess history
        game = Game.objects.get(id=self.game_id)
        player = Player.objects.create(user=self.user1, game=game)
        GuessHistory.objects.create(
            player=player,
            game=game,
            letter='p',
            is_correct=True,
            points=10
        )

        response = self.client.get(f'/api/games/{self.game_id}/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['letter'], 'p')

    def test_check_expired_games(self):
        # Create a game that should be expired
        expired_game = Game.objects.create(
            creator=self.user1,
            word='hello',
            status=2,  # Active
            max_attempts=6,
            attempts_left=3,
            created_at=timezone.now() - timedelta(days=2)  # Should be expired
        )

        # Get the game list which should trigger expiry check
        response = self.client.get('/api/games/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that game status was updated
        expired_game.refresh_from_db()
        self.assertEqual(expired_game.status, 3)  # Should be updated to completed status


class PlayerViewSetTests(APITestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(username='testuser1', password='password123')
        self.user2 = User.objects.create_user(username='testuser2', password='password123')

        # Create test games
        self.game1 = Game.objects.create(
            creator=self.user1,
            word='hello',
            status=2,
            max_attempts=6
        )

        self.game2 = Game.objects.create(
            creator=self.user1,
            word='world',
            status=2,
            max_attempts=6
        )

        # Create test players
        self.player1 = Player.objects.create(user=self.user1, game=self.game1, score=100)
        self.player2 = Player.objects.create(user=self.user2, game=self.game1, score=50)
        self.player3 = Player.objects.create(user=self.user1, game=self.game2, score=75)

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

    def test_list_players(self):
        response = self.client.get('/api/players/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        # Check ordering by score
        self.assertEqual(response.data[0]['score'], 100)
        self.assertEqual(response.data[1]['score'], 75)
        self.assertEqual(response.data[2]['score'], 50)

    def test_filter_players_by_game(self):
        response = self.client.get('/api/players/', {'game': self.game1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        response = self.client.get('/api/players/', {'game': self.game2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_player(self):
        response = self.client.get(f'/api/players/{self.player1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.player1.id)
        self.assertEqual(response.data['score'], 100)


class WordBankViewSetTests(APITestCase):
    def setUp(self):
        # Create test users
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.admin = User.objects.create_superuser(username='admin', password='admin123')

        # Create test words
        self.word1 = WordBank.objects.create(word='python', category='programming')
        self.word2 = WordBank.objects.create(word='django', category='framework')

        # Create API client
        self.client = APIClient()

    def test_list_words_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/words/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_words_as_user(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/words/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_word_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        data = {'word': 'javascript', 'category': 'programming'}
        response = self.client.post('/api/words/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WordBank.objects.count(), 3)

    def test_create_word_as_user(self):
        self.client.force_authenticate(user=self.user)
        data = {'word': 'javascript', 'category': 'programming'}
        response = self.client.post('/api/words/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(WordBank.objects.count(), 2)

    def test_update_word_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        data = {'word': 'python3', 'category': 'programming language'}
        response = self.client.put(f'/api/words/{self.word1.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.word1.refresh_from_db()
        self.assertEqual(self.word1.word, 'python3')
        self.assertEqual(self.word1.category, 'programming language')

    def test_delete_word_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/words/{self.word1.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(WordBank.objects.count(), 1)
