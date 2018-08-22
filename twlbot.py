import pywikibot
import json
import re
import urllib
import logging

logger = logging.getLogger(__name__)

site = pywikibot.Site()

TWLJ = 'User:TWLBot/sandbox'
with open('library_card_partners.json', encoding='utf-8') as json_file:
    library_card_partners = json.loads(json_file.read())


def can_bot_run():
    """
    Checks User:TWLBot/run, an openly editable page, to see if an editor
    has disabled the bot. If the page contains anything other than "yes",
    don't run.
    """
    run_page_name = "User:TWLBot/run"
    run_page = pywikibot.Page(site, run_page_name)

    if run_page.text == "yes":
        return True
    else:
        log_text = "{run_page_name} not set to 'yes', not running.".format(
            run_page_name = run_page_name
        )
        logger.error(log_text)
        return False


def extract_partner(wp_string):
    """
    Given a string containing a single internal or external link,
    extract the link text, in this case the partner name. Return None
    if there is any difficulty locating the name.
    """
    if "[[" in wp_string:
        regex = "\|([^]]+)\]\]"
    elif "wikipedialibrary.wmflabs" in wp_string:
        regex = "\/ ([^]]+)\]"
    else:
        return None

    try:
        found = re.search(regex, wp_string).group(1)
    except AttributeError:
        logger.info("Couldn't find partner in wp_string")
        found = None

    return found


def process_twlj():
    """
    Update Template:TWLJ with the latest status of all partners
    the code can identify on the Library Card platform. Only updates
    with available or waitlisted statuses.
    Whenever the code hits a line it doesn't know what to do with,
    it just retains the original text and moves on.
    """
    page = pywikibot.Page(site, TWLJ)
    text = page.text

    process_line = True
    final_page_text = []
    original_page_text = text

    for page_line in text.split("\n"):
        if "below" in page_line:
            # We've hit the end of the list of partners, don't
            # modify the remaining lines.
            process_line = False

        if page_line.startswith("*") and process_line:
            partner = extract_partner(page_line)
            try:
                lcp_number = library_card_partners[partner]
            except KeyError:
                logger.info("Couldn't find {partner} in "
                      "library_card_partners.json.".format(partner=partner))
                final_page_text.append(page_line)
                continue

            regex = "^[^\{{]+"
            try:
                without_twlavail = re.search(regex, page_line).group(0)
            except AttributeError:
                logger.info("Couldn't find {{twlavail}}, skipping.")
                final_page_text.append(page_line)
                continue

            lcp_page = "https://wikipedialibrary.wmflabs.org/partners/{pk}".format(
                pk=lcp_number
            )
            try:
                lcp_page_open = urllib.request.urlopen(lcp_page)
            except urllib.error.HTTPError:
                logger.info("404 on {partner}".format(partner=partner))
                final_page_text.append(page_line)
                continue

            lcp_page_text = lcp_page_open.read().decode('utf-8')
            if "Waitlisted" in lcp_page_text:
                status = "w"
            else:
                status = "y"

            # Appending {{twlavail}}. Quadruple { to escape properly in string.
            twlavail = " {{{{twlavail|{y_or_w}}}}}".format(y_or_w=status)
            page_line = without_twlavail.strip() + twlavail

        final_page_text.append(page_line)

    joined_page_text = "\n".join(final_page_text)
    # Only update if we've got a change.
    if original_page_text != joined_page_text:
        page.text = joined_page_text
        page.save("Updating availability")


if can_bot_run():
    process_twlj()
