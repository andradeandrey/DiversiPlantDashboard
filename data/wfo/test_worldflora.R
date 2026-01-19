# Test WorldFlora R package

# Check if WorldFlora is installed
if (!require("WorldFlora", quietly = TRUE)) {
    install.packages("WorldFlora", repos="https://cloud.r-project.org")
}
library(WorldFlora)
cat("WorldFlora loaded successfully\n")

# Load the backbone data
backbone_path <- "/Users/andreyandrade/Code/DiversiPlantDashboard-sticky/data/wfo/classification.csv"
cat("Loading backbone from:", backbone_path, "\n")

# Read with proper settings for this file format
WFO.data <- read.table(backbone_path, sep="\t", header=TRUE, quote="\"",
                       fill=TRUE, stringsAsFactors=FALSE, encoding="UTF-8")
cat("Loaded", nrow(WFO.data), "records\n")
cat("Columns:", paste(names(WFO.data), collapse=", "), "\n")

# Test with a few species
test_names <- c("Araucaria angustifolia", "Passiflora edulis", "Euterpe edulis", "Invalid species name")
cat("\nTesting WFO.match with:", paste(test_names, collapse=", "), "\n")

result <- WFO.match(spec.data = test_names, WFO.data = WFO.data, verbose = FALSE)
print(result[, c("spec.name.ORIG", "scientificName", "taxonomicStatus", "Matched", "Fuzzy")])
