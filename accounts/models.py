from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    level = models.IntegerField(default=1)
    xp = models.IntegerField(default=0)
    coin = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

    def calculate_xp_for_level(self, level):
        if level <= 1:
            return 0

        base_xp = 100

        total_xp = 0

        for lvl in range(1, level):
            level_xp = base_xp + (lvl - 1) * 50
            total_xp += level_xp

        return total_xp

    def get_xp_for_next_level(self):
        current_level_xp = self.calculate_xp_for_level(self.level)
        next_level_xp = self.calculate_xp_for_level(self.level + 1)
        return next_level_xp - current_level_xp

    def get_xp_progress(self):
        current_level_total_xp = self.calculate_xp_for_level(self.level)
        next_level_total_xp = self.calculate_xp_for_level(self.level + 1)

        xp_in_current_level = self.xp - current_level_total_xp

        xp_needed_for_next_level = next_level_total_xp - current_level_total_xp

        if xp_needed_for_next_level > 0:
            percentage = (xp_in_current_level / xp_needed_for_next_level) * 100
            return min(percentage, 100)  # Cap at 100%
        return 100  # Default if calculation not possible

    def add_xp(self, amount):
        if amount <= 0:
            return False, 0

        old_level = self.level
        self.xp += amount

        new_level = old_level
        while True:
            xp_needed = self.calculate_xp_for_level(new_level + 1)
            if self.xp >= xp_needed:
                new_level += 1
            else:
                break

        levels_gained = new_level - old_level
        leveled_up = levels_gained > 0

        if leveled_up:
            self.level = new_level

        self.save()
        return leveled_up, levels_gained

    def add_coins(self, amount):
        if amount > 0:
            self.coin += amount
            self.save()
            return True
        return False

    def deduct_coins(self, amount):
        if 0 < amount <= self.coin:
            self.coin -= amount
            self.save()
            return True
        return False

    def add_score(self, amount):
        if amount > 0:
            self.score += amount
            self.save()
            return True
        return False
