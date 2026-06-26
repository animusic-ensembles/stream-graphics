from pathlib import Path
import credits.app as Credits
import lower_thirds.app as LowerThirds

filename = Path('csv/W26 EOT Credits.csv')

setlist = Credits.generate(filename)
LowerThirds.generate(setlist)