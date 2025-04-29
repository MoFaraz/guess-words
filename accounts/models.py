from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    score = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    xp = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

    def calculate_xp_for_level(self, level):
        """
        Calculate XP required for a specific level using a progressive formula
        Base XP: 100 for level 1
        Each subsequent level requires 50 more XP than the previous level increment
        Example:
        - Level 1 to 2: 100 XP
        - Level 2 to 3: 150 XP (100 + 50)
        - Level 3 to 4: 200 XP (150 + 50)
        - Level 4 to 5: 250 XP (200 + 50)
        And so on...
        """
        if level <= 1:
            return 0

        # Base XP for level 1 to 2
        base_xp = 100

        # XP required for level
        total_xp = 0

        for lvl in range(1, level):
            level_xp = base_xp + (lvl - 1) * 50
            total_xp += level_xp

        return total_xp

    def get_xp_for_next_level(self):
        """Get XP required to reach the next level from current level"""
        current_level_xp = self.calculate_xp_for_level(self.level)
        next_level_xp = self.calculate_xp_for_level(self.level + 1)
        return next_level_xp - current_level_xp

    def get_xp_progress(self):
        """Get current progress towards next level as percentage"""
        current_level_total_xp = self.calculate_xp_for_level(self.level)
        next_level_total_xp = self.calculate_xp_for_level(self.level + 1)

        # XP in current level
        xp_in_current_level = self.xp - current_level_total_xp

        # XP needed for next level
        xp_needed_for_next_level = next_level_total_xp - current_level_total_xp

        # Calculate percentage (avoid division by zero)
        if xp_needed_for_next_level > 0:
            percentage = (xp_in_current_level / xp_needed_for_next_level) * 100
            return min(percentage, 100)  # Cap at 100%
        return 100  # Default if calculation not possible

    def add_xp(self, amount):
        """
        Add XP to user and update level if threshold is reached
        Returns: tuple (leveled_up, levels_gained)
        """
        if amount <= 0:
            return False, 0

        old_level = self.level
        self.xp += amount

        # Find appropriate level based on total XP
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

