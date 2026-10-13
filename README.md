# Job Finder

Uploaded PDF CVs populate professional profile details. The parser recognizes
compound headings such as Technical Skills and Professional Profile, and headings
with trailing qualifiers such as Professional Experience - Software Development.
Repeated sections accumulate in document order, including separate experience and
academic project blocks. Leadership and volunteering, academic research and
projects, and training and credentials populate the `volunteering`, `projects`,
and `trainings` profile fields. References stop section content collection.
Empty parsed fields preserve existing profile values.

## Profile form

The guided form starts with PDF upload instructions. Check your contact details,
upload your CV, then click **Analyze CV** (**Analizar CV** in Spanish). Review and
edit the extracted content in the tabs: summary, skills, experience, volunteering,
projects, education, trainings, certifications, languages, and additional information.
Volunteering and projects sit beside experience; trainings sit beside certifications.
The parser behavior and three dedicated fields described above shipped in T-56-1;
this form layout adds guidance and makes those fields available for review.
