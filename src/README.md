# BuiltBy Data

## New Projects

### Procedure

1. Make a request to the URL for the RSS feed.
2. If a project does not exist in the database, parse the html div and add the result to the database.
3. Check if a project exists by first checking the project number, then the address, and then the description, and then the design review link.
4. If all attributes match, load the object as a dict and update the fields one-by-one if the new attribute is not None.
5. If the attributes do not match, add the project as if it were a separate project.

### Resolve Missing Information

#### Latitude and Longitude

1. For each object in the database, check if latitude and longitude is not None.


#### Design Proposal Cover

1. For each object in the database, check there is a link to a design proposal.
2. Check if the last three characters in the URL is pdf.
3. Convert the first page to an image, save to s3, add link to url to database.


### Project Schema


## Check RSS Feed Daily
1. Load existing mongodb.
2. Get last published date.
3. Make request to RSS feed to get list of links.
4. Parse links to check published date.
5. Remove project links that are older than last published .
6. Package approved projects and format as JSON or dict.
    * RSS HTML -> PROJECT OBJECT -> GET_LATLON -> GET IMAGE ->  -> LOAD INTO MONGODB
7. Add these projects to the database.
