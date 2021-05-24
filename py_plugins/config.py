# Tag name used for selecting scenes to bulk scrape
control_tag = '0.Scrape'

# Create missing performers/tags/studios
# Default: False (Prevent Stash from getting flooded with weird values)
create_missing_performers = False
create_missing_tags = False
create_missing_studios = False

# Regular expression pattern for matching performer 'First Last' name (seperated
# with space, underscore or period) from filename.
parse_performer_pattern = r'^.*[ \._]([A-Z][a-zA-Z]+)[ \._]([A-Z][a-zA-Z]*)[ \._].*$'

# Delay between web requests
delay = 5  # Default: 5
