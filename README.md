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
Empty parsed fields preserve existing profile values.
Spoken languages are kept separate from programming skills. Personal website and
GitHub links in the contact header populate additional information, while LinkedIn
keeps its own field. Training and credentials remain complete in trainings; only
entries explicitly labelled certificate or licence are also copied to certifications.
Credential wording and stated status are preserved without inferring validity.

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
