"""A player's champion points follow the log: a returning player takes the
figure of the line that adds them again, not the one stored when first seen,
and a UNIT_CHANGED with new champion points updates the row."""

import unittest

from tests.fixtures.build_session import SESSION, fights


def _cp(entry, handle='@brainsnorkel'):
    return next(p['cp'] for p in entry.players if p['name'] == handle)


class TestChampionPointsUpdate(unittest.TestCase):

    def test_first_session_as_logged(self):
        (entry,) = fights()
        self.assertEqual(_cp(entry), 3224)

    def test_returning_player_takes_the_new_figure(self):
        second = [line.replace('1759600000000', '1759700000000')
                       .replace('"@brainsnorkel",14901578173200504511,50,3224',
                                '"@brainsnorkel",14901578173200504511,50,3225')
                  for line in SESSION]
        first, again = fights(SESSION + second)
        self.assertEqual(_cp(first), 3224)
        self.assertEqual(_cp(again), 3225)

    def test_unit_changed_updates_champion_points(self):
        changed = ('3000,UNIT_CHANGED,1,1,4,"Pïque","@brainsnorkel",'
                   '14901578173200504511,50,3230,0,PLAYER_ALLY,T')
        cut = SESSION.index('9990,BEGIN_COMBAT')
        (entry,) = fights(SESSION[:cut] + [changed] + SESSION[cut:])
        self.assertEqual(_cp(entry), 3230)

    def test_unit_changed_without_champion_points_keeps_them(self):
        changed = ('3000,UNIT_CHANGED,1,1,4,"Pïque","@brainsnorkel",'
                   '14901578173200504511,50,0,0,PLAYER_ALLY,T')
        cut = SESSION.index('9990,BEGIN_COMBAT')
        (entry,) = fights(SESSION[:cut] + [changed] + SESSION[cut:])
        self.assertEqual(_cp(entry), 3224)


if __name__ == '__main__':
    unittest.main()
