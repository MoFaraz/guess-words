from django.contrib import admin

from game.models import Game, WordBank, GuessHistory, GameHistory

# Register your models here.
admin.site.register(Game)
admin.site.register(WordBank)
admin.site.register(GuessHistory)
admin.site.register(GameHistory)

