# data/

One subfolder per dataset, created with `smairt data new NAME`. Each README's
frontmatter records every place the dataset's bytes actually live (local path, HPC
host + path, or a source URL) — add more with `smairt data locate NAME`, see them
all with `smairt data list`. Below the frontmatter: free-form provenance prose,
where the data came from, when, and any transform already applied before it landed
here. Data file contents are git-ignored by default (see .gitignore); only the
READMEs are tracked.
