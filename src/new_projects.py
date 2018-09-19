import datetime
import requests
from bs4 import BeautifulSoup

import json
import plac

from utils.geo import get_latlon
from utils.pdf import download_and_convert_pdf
from utils.mongo import (load_collection, write_collection, write_doc,
                         delete_collection, update_doc)


""" GENERAL FUNCTIONS """
""" ----------------- """


def load_json(path):
    """Load existing json file for new_projects
    """
    with open(path, 'r') as f:
        new_projects = json.load(f)

    return new_projects


def write_to_json(data, path):
    """Write to list of dictionaries to a JSON file
    """
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


def get_last_date(data, k='published_date'):
    """Extracts the date field for each item in the dict and returns the most
    recent date.

    Arguments:
        data (list of dict or JSON)
    Return:
        last_date as string in format MM/DD/YYYY
    """
    dates = []
    for item in data:
        date_item = datetime.datetime.strptime(item[k], '%m/%d/%Y')
        dates.append(date_item)
    last_date = max(dates)
    return last_date.strftime('%m/%d/%Y')


def package_new_projects(projects_list, path):
    """Creates meta data object and saves the new projects under the 'data' key

    -- FOR JSON FILES ONLY --
    """
    last_run_date = datetime.datetime.now().strftime('%m/%d/%Y')
    last_pub_date = get_last_date(projects_list, k='published_date')
    new_projects_obj = {}  # empty object container
    new_projects_obj['meta'] = {
        'last_pub_date': last_pub_date,
        'last_run_date': last_run_date}
    new_projects_obj['data'] = projects_list
    return new_projects_obj


""" CREATING PROJECTS """
""" ----------------- """


def get_rss_items(rss_url):
    """Returns the HTML elements in the RSS feed

    Arguments:
        rss_url (str): URL to RSS feed

    Returns:
        items (list of div elements)
    """
    response = requests.get(rss_url)
    html = response.content
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.select('item')  # each item is a different permit
    return items


def create_project_obj(elem):
    """Creates a project JSON object when given an HTML element from the
    RSS feed.

    Arguments:
        elem (html element)
    Returns:
        project (dict)
    """
    # get todays date in MM/DD/YYYY format as string
    today = datetime.datetime.now().strftime('%m/%d/%Y')

    project = {}  # create empty dictionary
    link = elem.select_one('link').text.strip()
    published_date = elem.select_one('pubdate').text.split()[0]
    title = elem.select_one('title').text.strip()
    project_review_date = title.split(' - ')[0]
    review_desc = elem.select_one('description').text.strip()

    # parse review_desc
    review_board = review_desc.split(' - ')[0]
    meeting_details = review_desc.split(' - ')[1]

    # build project dict
    project = {
        'title': title,
        'published_date': published_date,
        'project_review_date': project_review_date,
        'design_review_link': link,
        'review_board': review_board,
        'meeting_details': meeting_details,
        'found_date': today
    }

    return project


def parse_proposal_page(project):
    """Parses the specific proposal page for each project to get more
    information.

    Arguments:
        project (dict)

    Returns:
        project (dict): new attributes include address, project_num,
            description, design_proposal_link, report_link, past_reviews_link
    """
    project_name = project['title']
    print(f"Parsing design proposal info for {project_name} ...")

    url = project['design_review_link']
    baseurl = url.split('/Detail')[0]
    resp = requests.get(url)
    if resp.status_code == 200:
        html = resp.content
        soup = BeautifulSoup(html, 'html.parser')
        description = soup.select_one(
            'div#dvDataFound p span#lblDescription').text
        address = soup.select_one('span#lblAddress').text

        project_num = soup.select_one('div span#lblProject').text
        project['address'] = address
        project['description'] = description
        project['project_num'] = project_num

        # check for design proposal and report PDFs
        design_proposal = soup.select_one('a#hypProposal')
        if design_proposal is not None:
            design_proposal_link = design_proposal['href']
            project['design_proposal_link'] = design_proposal_link

        report = soup.select_one('a#hypReport')
        if report is not None:
            report_link = report['href']
            project['report_link'] = report_link

        # check for past reviews
        past_reviews = soup.select_one('a#hypPastReviews')
        if past_reviews is not None:
            past_reviews_link = baseurl + past_reviews['href'].lstrip('..')
            project['past_reviews_link'] = past_reviews_link

    return project


def load_project(project, dbname='builtby', coll='new_projects'):
    """Load a project document into a MongoDB collection

    Before a project is loaded, check if the project already exists in the
    database.

    Returns:
        None
    """
    # get attributes to check for existing
    project_num = project['project_num']
    address = project['address']
    description = project['description']
    design_review_link = project['design_review_link']

    # get mongo cursor for local collection
    projects_cursor = load_collection('builtby', 'new_projects')

    # existing will be a list of documents matching the attributes
    existing = projects_cursor.find({
        'project_num': project_num,
        'address': address,
        'description': description,
        'design_review_link': design_review_link
    })

    if len(list(existing)) == 0:
        write_doc(dbname, coll, project)


def package_project(project):
    """Add supplemental info to project and return it back

    Arguments:
        project (dict)
    Returns:
        project (dict)
    """

    project = parse_proposal_page(project)
    project = add_lat_lon(project)
    if 'design_proposal_link' in project.keys():
        print("This project has a design proposal")
        project = get_project_image(project)
    return project


def create_new_projects_db(dbname='builtby', coll='new_projects',
                           overwrite=False):
    """Creates a new collection and loads the collection with projects

    Returns:
        None
    """
    if overwrite:
        delete_collection(dbname, coll)

    base_url = "http://www.seattle.gov/DPD/aboutus/news/events/DesignReview/"
    rss_url = "{}upcomingreviews/RSS.aspx".format(base_url)

    # get rss html items
    items = get_rss_items(rss_url)
    print(f"Found {len(items)} items.")

    # upcoming_projects = []  # container for list of dictionaries
    # create project objects
    for item in items:
        project = create_project_obj(item)
        document = package_project(project)  # send project through pipeline
        load_project(document)


""" SUPPLEMENTING PROJECT INFO """
""" -------------------------- """


def add_lat_lon(project):
    """Uses Google Map's API to get the latitude and longitude values
    """
    project_address = project['address']
    print(f"Getting latitude and longitude for {project_address} ...")

    if 'latitude' not in project.keys():
        full_address = project['address'] + ' Seattle, WA'
        lat, lon = get_latlon(full_address)

        project['latitude'] = lat
        project['longitude'] = lon
    return project


def resolve_geo_attr_json(path):
    with open(path, 'r') as f:
        new_projects = json.load(f)

    projects = new_projects['data']

    for project in projects:
        if project['latitude'] is None:
            full_address = project['address'] + ' Seattle, WA'
            print(f"Attempting to retrieve lat and lon for {full_address}")
            lat, lon = get_latlon(full_address)

            project['latitude'] = lat
            project['longitude'] = lon

    return projects


def resolve_geo_attr_mongo(cursor):
    projects = cursor.find()
    for project in projects:
        if project['latitude'] is None:
            full_address = project['address'] + ', Seattle, WA'
            print(f"Attempting to retrieve lat and lon for {full_address}")
            lat, lon = get_latlon(full_address)
            if lat is not None:
                project['latitude'] = lat
                project['longitude'] = lon
                update_doc('builtby', 'new_projects', project, 'latitude',
                           'longitude')

    return projects


def get_project_image(project):
    """Add project image url to project document
    """

    dp_pdf_link = project['design_proposal_link']
    project_address = project['address']
    print(f"Checking design proposal at {dp_pdf_link}")
    if dp_pdf_link is not None:
        if 'dpimage_url' not in project.keys():
            if dp_pdf_link.split('.')[-1] == 'pdf':
                try:
                    print(f"Obtaining image for {project_address}")
                    png_fname = download_and_convert_pdf(dp_pdf_link)

                    s3_url = "https://s3-us-west-2.amazonaws.com/builtby/"

                    project['dpimage_url'] = s3_url + png_fname
                except Exception as exc:
                    print(f"Encountered error with {project_address}")
                    print(exc)
    return project


def update_new_projects_db(path_to_json):
    """Adds new items to an existing JSON file
    """
    base_url = "http://www.seattle.gov/DPD/aboutus/news/events/DesignReview/"
    rss_url = "{}upcomingreviews/RSS.aspx".format(base_url)

    # get rss html items
    items = get_rss_items(rss_url)

    new_projects = load_json(path_to_json)

    last_pub_date = new_projects['meta']['last_pub_date']

    newly_published_projects = []  # container for list of dictionaries

    # create project objects
    for item in items:
        project = create_project_obj(item)
        if project['published_date'] > last_pub_date:
            newly_published_projects.append(project)

    # print to console the number of projects found
    num_projects = len(newly_published_projects)
    print(f"Found {num_projects} project(s).")

    # add design proposal information to project object
    for project in newly_published_projects:
        project = parse_proposal_page(project)

    # add latitude and longitude data to project object
    for project in newly_published_projects:
        project = add_lat_lon(project)

    combined = new_projects['data']
    combined.extend(newly_published_projects)
    return combined


@plac.annotations(
    new=("Create new collection", "flag", "n"),
    overwrite=("Overwrite the existing collection", "flag", "o"),
    to_json=("Convert mongo collection to json", "flag", None),
    to_mongo=("Convert json to mongo", "option", None),
    resolve_geo=("Resolve missing lat and lon info", "flag", None)
    )
def main(new=False, overwrite=False, to_json=False, to_mongo=None,
         resolve_geo=False):
    """Creates or updates a JSON file with projects from an RSS feed."""
    if new:
        create_new_projects_db(dbname='builtby', coll='new_projects',
                               overwrite=overwrite)
        # package_new_projects(new_projects, path)
    elif to_json:
        projects = load_collection(dbname='builtby', coll='new_projects',
                                   to_json=to_json)
        # print(projects)
        for project in projects:
            if '_id' in project:
                del project['_id']

        path = "../data/new_projects.json"
        write_to_json(projects, path)
    elif to_mongo is not None:
        path = to_mongo
        projects = load_json(path)
        write_collection(dbname='builtby', coll='new_projects', data=projects,
                         delete_existing=True)
    elif resolve_geo:
        projects = load_collection(dbname='builtby', coll='new_projects')
        resolve_geo_attr_mongo(projects)

    else:
        print("Hello world!")


if __name__ == "__main__":
    plac.call(main)
