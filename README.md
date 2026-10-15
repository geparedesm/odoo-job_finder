# Job Finder

Uploaded PDF CVs populate professional profile details. The parser recognizes
compound headings such as Technical Skills and Professional Profile, and headings
with trailing qualifiers such as Professional Experience - Software Development.
Repeated sections accumulate in document order, including separate experience and
academic project blocks. Leadership and volunteering, academic research and
projects, and training and credentials populate the `volunteering`, `projects`,
and `trainings` profile fields. References stop section content collection.
Location is extracted from delimited contact lines. Repeated name/subtitle page
headers and name/page-count footers are excluded from section content.
Spoken languages labeled `Languages spoken` or under `Language`/`Languages` populate `languages`, while
programming languages remain in skills. Header website and GitHub links populate
`extra_info`; LinkedIn populates its dedicated field. Training and Credentials is
retained in full in `trainings`. Entries explicitly mentioning a licence,
certificate or certified status are also copied verbatim to `certifications`,
including statuses such as Current and Not renewed, without inferring validity.
Only explicitly authorized profile fields are saved. Empty parsed fields preserve
existing profile values.

Regression fixtures include the complete six-page reference PDF, its extracted
text and exact expected values for every field. Odoo tests parse and save the real
PDF without mocking the parser, then check preservation after empty/invalid input.

## Profile form

The guided form starts with contact details, followed by PDF upload instructions. The header provides the analysis and download actions.
Upload your CV, then click **Analyze CV** (**Analizar CV** in Spanish). Review and
edit the extracted content in the tabs: summary, skills, experience, education,
volunteering, projects, trainings, certifications, languages, and additional information.
Each tab includes a placeholder suggesting which details to include.
The parser behavior and three dedicated fields described above shipped in T-56-1;
this form layout adds guidance and makes those fields available for review.

## Download the complete CV

Save your profile edits, then click **Download complete CV** in the form header
(**Descargar CV completo** in Spanish), or select **Complete CV** from the Print menu.
The PDF includes your current name, headline, contact data, summary, skills,
experience, education, volunteering, projects, trainings, certifications, languages,
and additional information. Multiline entries retain their line breaks; empty sections
are omitted. You can download a manually completed profile without uploading a PDF.

Downloads are generated afresh from saved profile values, including additions made
after parsing. The original uploaded file and parser diagnostics remain available in
Odoo; they are not appended to the professional CV. Existing profile access rules also
apply to downloads, so users can only download profiles they are allowed to read.
