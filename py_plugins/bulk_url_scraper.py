import json
import sys
from urllib.parse import urlparse
import time
import re
import os

import log
import config
from stash_interface import StashInterface

# Name of the tag, that will be used for selecting scenes for bulk scraping
try:
    control_tag = config.control_tag
except AttributeError:
    control_tag = '0.Scrape'


def main():
    json_input = read_json_input()

    output = {}
    run(json_input, output)

    out = json.dumps(output)
    print(out + "\n")


# Waits the remaining time between the last timestamp and the configured delay in seconds
def wait(delay, time_last, time_now):
    time_last = int(time_last)
    time_now = int(time_now)
    if time_now > time_last:
        if time_now - time_last < delay:
            time.sleep(delay - (time_now - time_last) + 1)


def read_json_input():
    json_input = sys.stdin.read()
    return json.loads(json_input)


def run(json_input, output):
    mode_arg = json_input['args']['mode']

    try:
        if mode_arg == "" or mode_arg == "scrape":
            client = StashInterface(json_input["server_connection"])
            bulk_scrape(client)
        elif mode_arg == "scrapeurl":
            client = StashInterface(json_input["server_connection"])
            bulk_scrape_scene_url(client)
        elif mode_arg == "createperformer":
            client = StashInterface(json_input["server_connection"])
            bulk_create_performer(client)
        elif mode_arg == "create":
            client = StashInterface(json_input["server_connection"])
            add_tag(client)
        elif mode_arg == "remove":
            client = StashInterface(json_input["server_connection"])
            remove_tag(client)
    except Exception:
        raise

    output["output"] = "ok"


def __bulk_scrape(client, scenes, create_missing_performers=False, create_missing_tags=False, create_missing_studios=False, delay=5):
    last_request = -1
    if delay > 0:
        # Initialize last request with current time + delay time
        last_request = time.time() + delay

    missing_scrapers = list()

    # Number of scraped scenes
    count = 0

    total = len(scenes)
    # Index for progress bar
    i = 0

    # Scrape if url not in missing_scrapers
    for scene in scenes:
        # Update status bar
        i += 1
        log.LogProgress(i/total)

        if scene.get('url') is None or scene.get('url') == "":
            log.LogInfo(f"Scene {scene.get('id')} is missing url")
            continue
        if urlparse(scene.get("url")).netloc not in missing_scrapers:
            if delay:
                wait(delay, last_request, time.time())
            scraped_data = client.scrapeSceneURL(scene.get('url'))
            # If result is null, add url to missing_scrapers
            if scraped_data is None:
                log.LogWarning(f"Missing scraper for {urlparse(scene.get('url')).netloc}")
                missing_scrapers.append(urlparse(scene.get('url')).netloc)
                continue
            # No data has been found for this scene
            if not any(scraped_data.values()):
                log.LogInfo(f"Could not get data for scene {scene.get('id')}")
                continue

            # Create dict with scene data
            update_data = {
                'id': scene.get('id')
            }
            if scraped_data.get('title'):
                update_data['title'] = scraped_data.get('title')
            if scraped_data.get('details'):
                update_data['details'] = scraped_data.get('details')
            if scraped_data.get('date'):
                update_data['date'] = scraped_data.get('date')
            if scraped_data.get('image'):
                update_data['cover_image'] = scraped_data.get('image')
            if scraped_data.get('tags'):
                tag_ids = list()
                for tag in scraped_data.get('tags'):
                    if tag.get('stored_id'):
                        tag_ids.append(tag.get('stored_id'))
                    else:
                        if create_missing_tags and tag.get('name') != "":
                            # Capitalize each word
                            tag_name = " ".join(x.capitalize() for x in tag.get('name').split(" "))
                            log.LogInfo(f'Create missing tag: {tag_name}')
                            tag_id = client.createTagWithName(tag_name)
                            tag_ids.append(tag_id)
                if len(tag_ids) > 0:
                    update_data['tag_ids'] = tag_ids

            if scraped_data.get('performers'):
                performer_ids = list()
                for performer in scraped_data.get('performers'):
                    if performer.get('stored_id'):
                        performer_ids.append(performer.get('stored_id'))
                    else:
                        if create_missing_performers and performer.get('name') != "":
                            performer_name = " ".join(x.capitalize() for x in performer.get('name').split(" "))
                            log.LogInfo(f'Create missing performer: {performer_name}')
                            performer_id = client.createPerformerByName(performer_name)
                            performer_ids.append(performer_id)
                if len(performer_ids) > 0:
                    update_data['performer_ids'] = performer_ids

            if scraped_data.get('studio'):
                studio = scraped_data.get('studio')
                if studio.get('stored_id'):
                    update_data['studio_id'] = studio.get('stored_id')
                else:
                    if create_missing_studios:
                        studio_name = " ".join(x.capitalize() for x in studio.get('name').split(" "))
                        log.LogInfo(f'Creating missing studio {studio_name}')
                        studio_url = '{uri.scheme}://{uri.netloc}'.format(uri=urlparse(scene.get('url')))
                        studio_id = client.createStudio(studio_name, studio_url)
                        update_data['studio_id'] = studio_id

            # Update scene with scraped scene data
            client.updateScene(update_data)
            log.LogDebug(f"Scraped data for scene {scene.get('id')}")
            count += 1

    return count

def __bulk_scrape_scene_url(client, scenes, delay=5):
    last_request = -1
    if delay > 0:
        # Initialize last request with current time + delay time
        last_request = time.time() + delay

    # Number of scraped scenes
    count = 0

    total = len(scenes)
    # Index for progress bar
    i = 0

    # Scrape scene with existing metadata
    for scene in scenes:
        # Update status bar
        i += 1
        log.LogProgress(i/total)

        if delay:
            wait(delay, last_request, time.time())

        # Create dict with scene data
        scene_data = {
            'id': scene.get('id'),
        }

        # Extract scraper ID if appended to control tag, then scrape scene
        if '_' in control_tag:
            scraper_id = control_tag.split('_')[-1]
            scraped_data = client.scrapeScene(scene_data, scraper_id)
        else:
            scraped_data = client.scrapeScene(scene_data)

        # No data has been found for this scene
        if not any(scraped_data.values()):
            log.LogInfo(f"Could not get data for scene {scene.get('id')}")
            continue

        # Create dict with scene data
        update_data = {
            'id': scene.get('id')
        }
        if scraped_data.get('url'):
            update_data['url'] = scraped_data.get('url')

        # Update scene with scraped scene data
        client.updateScene(update_data)
        log.LogDebug(f"Scraped data for scene {scene.get('id')}")
        count += 1

    return count

def __bulk_create_performer(client, scenes, create_missing_performers, parse_performer_pattern, delay):
    last_request = -1
    if delay > 0:
        # Initialize last request with current time + delay time
        last_request = time.time() + delay

    # Number of created performers
    count = 0

    total = len(scenes)
    # Index for progress bar
    i = 0

    # List all performers in database
    all_performers = client.listPerformers()

    for scene in scenes:
        # Update status bar
        i += 1
        log.LogProgress(i/total)

        if scene.get('path') is None or scene.get('path') == "":
            log.LogInfo(f"Scene {scene.get('id')} is missing path")
            continue

        # Parse performer name from scene basename file path
        scene_basename = os.path.basename(scene['path'])
        log.LogInfo(f"Scene basename is: {scene_basename}")
        performer_regex = re.compile(parse_performer_pattern)
        parsed_performer_regex = performer_regex.search(scene_basename)
        if parsed_performer_regex is None:
            log.LogInfo(f"No Performer found Scene {scene.get('id')} filename")
            continue
        parsed_performer_name = ' '.join(parsed_performer_regex.groups())
        log.LogInfo(f"Parsed performer name is: {parsed_performer_name}")

        # If performer name successfully parsed from scene basename
        if parsed_performer_name:
            # Create dict with scene data
            update_data = {
                'id': scene.get('id')
            }

            # List all performers currently attached to scene
            scene_performers = [sp['name'].lower() for sp in scene['performers']]
            log.LogInfo(f"Current scene performers are: {scene_performers}")

            # Check if performer already attached to scene
            performer_ids = list()
            if parsed_performer_name.lower() in scene_performers:
                continue
            else:
                # Check if performer already exists in database
                for performer in all_performers:
                    if  performer['name'] and parsed_performer_name.lower() == performer['name'].lower():
                        performer_ids.append(performer['id'])
                        break
                    if performer['aliases'] and parsed_performer_name.lower() in [p.strip().lower() for p in performer['aliases'].replace('/', ',').split(',')]:
                        performer_ids.append(performer['id'])
                        break
                else:
                    # Create performer if not in database
                    if create_missing_performers and parsed_performer_name != "":
                        performer_name = " ".join(x.capitalize() for x in parsed_performer_name.split(" "))
                        log.LogInfo(f'Create missing performer: {performer_name}')
                        performer_id = client.createPerformerByName(performer_name)
                        performer_ids.append(performer_id)
                        # Add newly created performer to all performers list
                        all_performers.append({'id':performer_id, 'name':performer_name, 'aliases':''})

                # Add found/created performer IDs to scene update data
                if len(performer_ids) > 0:
                    update_data['performer_ids'] = performer_ids
                    log.LogInfo(f"Performer IDs found: {performer_ids}")

                # Update scene with parsed performer data
                client.updateScene(update_data)
                log.LogDebug(f"Updated performer data for scene {scene.get('id')}")
                count += 1

    return count


def bulk_scrape(client, create_missing_performers=False, create_missing_tags=False, create_missing_studios=False, delay=5):
    try:
        create_missing_studios = bool(config.create_missing_studios)
        create_missing_tags = bool(config.create_missing_tags)
        create_missing_performers = bool(config.create_missing_performers)
        delay = int(config.delay)
    except AttributeError as e:
        log.LogWarning(e)
        log.LogWarning("Using defaults for missing config values")
    except ValueError as e:
        log.LogWarning(e)
        log.LogWarning("Using defaults for wrong values")

    log.LogInfo('##### Bulk URL Scraper #####')
    log.LogInfo(f'create_missing_performers: {create_missing_performers}')
    log.LogInfo(f'create_missing_tags: {create_missing_tags}')
    log.LogInfo(f'create_missing_studios: {create_missing_studios}')
    log.LogInfo(f'delay: {delay}')
    log.LogInfo('#############################')

    # Search for all scenes with scrape tag
    tag = client.findTagIdWithName(control_tag)
    if tag is None:
        sys.exit("Tag scrape does not exist. Please create it via the 'Create scrape tag' task")

    tag_ids = [tag]
    scenes = client.findScenesByTags(tag_ids)
    log.LogInfo(f'Found {len(scenes)} scenes with scrape tag')
    count = __bulk_scrape(client, scenes, create_missing_performers, create_missing_tags, create_missing_studios, delay)
    log.LogInfo(f'Scraped data for {count} scenes')


def bulk_scrape_scene_url(client, delay=5):
    try:
        delay = int(config.delay)
    except AttributeError as e:
        log.LogWarning(e)
        log.LogWarning("Using defaults for missing config values")
    except ValueError as e:
        log.LogWarning(e)
        log.LogWarning("Using defaults for wrong values")

    log.LogInfo('##### Bulk Scene URL Scraper #####')
    log.LogInfo(f'delay: {delay}')
    log.LogInfo('#############################')

    # Search for all scenes with scrape tag
    tag = client.findTagIdWithName(control_tag)
    if tag is None:
        sys.exit("Tag scrape does not exist. Please create it via the 'Create scrape tag' task")

    tag_ids = [tag]
    scenes = client.findScenesByTags(tag_ids)
    log.LogInfo(f'Found {len(scenes)} scenes with scrape tag')
    count = __bulk_scrape_scene_url(client, scenes, delay)
    log.LogInfo(f'Scraped data for {count} scenes')


def bulk_create_performer(client, create_missing_performers=False, parse_performer_pattern=r'^.*[ \._]([A-Z][a-zA-Z]+)[ \._]([A-Z][a-zA-Z]+)[ \._].*$', delay=5):
    try:
        create_missing_performers = bool(config.create_missing_performers)
        parse_performer_pattern = config.parse_performer_pattern
        delay = int(config.delay)
    except AttributeError as e:
        log.LogWarning(e)
        log.LogWarning("Using defaults for missing config values")
    except ValueError as e:
        log.LogWarning(e)
        log.LogWarning("Using defaults for wrong values")

    log.LogInfo('##### Bulk Create Performer #####')
    log.LogInfo(f'create_missing_performers: {create_missing_performers}')
    log.LogInfo(f'parse_performer_pattern: {parse_performer_pattern}')
    log.LogInfo(f'delay: {delay}')
    log.LogInfo('#############################')

    # Search for all scenes with scrape tag
    tag = client.findTagIdWithName(control_tag)
    if tag is None:
        sys.exit("Scrape Tag does not exist. Please create it via the 'Create scrape tag' task")

    tag_ids = [tag]
    scenes = client.findScenesByTags(tag_ids)
    log.LogInfo(f'Found {len(scenes)} scenes with scrape tag')
    count = __bulk_create_performer(client, scenes, create_missing_performers, parse_performer_pattern, delay)
    log.LogInfo(f'Created {count} performers')


def add_tag(client):
    tag_id = client.findTagIdWithName(control_tag)

    if tag_id is None:
        client.createTagWithName(control_tag)
        log.LogInfo("Tag created successfully")
    else:
        log.LogInfo("Tag already exists")


def remove_tag(client):
    tag_id = client.findTagIdWithName(control_tag)

    if tag_id is None:
        log.LogInfo("Tag does not exist. Nothing to remove")
        return

    log.LogInfo("Destroying tag")
    client.destroyTag(tag_id)


main()
