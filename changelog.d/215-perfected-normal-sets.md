### Changed
- **A set worn partly perfected and partly normal is one entry on the gear line** (#215): `5x Slivers of the Null Arca (2 perfected)` in place of two entries that could sit far apart. The game counts the two versions together towards the set's bonuses, so the line now says what the player has. The name opens the normal version's ESO-Hub page and `2 perfected` the perfected one's, hovering either says `5 pieces: 2 perfected, 3 normal`, and Copy fight writes the same entry. Fights from before this version show it too
- **The gear line under each build card is larger** (#215): 0.85 of the pane's text size, the size of the scribed-skill line above it, up from 0.75, which was the smallest text in the app

### Fixed
- **Build checks and penetration count a set's perfected and normal pieces together** (#215): the app counted the two versions as two sets, so a build with two perfected and three normal pieces had five pieces in the game and none complete in the app. Checked on 411 logs: of 162 player sessions that reached five pieces only with both versions counted, 158 show the set's own effect, as 3,537 of 3,594 sessions with five pieces of one version do. What changes for those players:
  - a Lucent Echoes, Xoryn's Masterpiece or Pearlescent Ward the two versions complete on both bars is no longer called complete on one bar only, and one they complete on one bar only now is;
  - a Roaring Opportunist worn in both versions is judged by the never-fires rule;
  - three pieces of a trial set across both versions count as a Minor Slayer source;
  - the Pen and crit tab reads a set's lines once at the two counts added (two perfected and two normal pieces of Ansuul's Torment give its four-piece penetration), while a perfected arena weapon's own two-piece line still needs both pieces perfected;
  - the Build tab's Pcs column shows the pair's count on the rows of both versions
