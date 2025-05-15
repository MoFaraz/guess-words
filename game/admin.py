from django.contrib import admin

from game.models import Game, Player, WordBank, GuessHistory, GameHistory

# Register your models here.
admin.site.register(Game)
admin.site.register(Player)
admin.site.register(WordBank)
admin.site.register(GuessHistory)
admin.site.register(GameHistory)

