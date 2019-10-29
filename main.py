# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.4'
#       jupytext_version: 1.2.4
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # LTIM time series, 1991 to 2016 Age and Sex

# +
from gssutils import *

scraper = Scraper('https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/' \
                  'internationalmigration/datasets/longterminternationalmigrationageandsextable207')
scraper
# -

tab = next(t for t in scraper.distribution(mediaType=Excel).as_databaker() if t.name == 'Table 2.07')

# +
corner = tab.filter('Year')
corner.assert_one()

observations = corner \
    .shift(RIGHT) \
    .fill(DOWN) \
    .filter('Estimate') \
    .expand(RIGHT) \
    .filter('Estimate') \
    .fill(DOWN) \
    .is_not_blank() \
    .is_not_whitespace() \
    .filter(lambda x: type(x.value) != str or 'Statistically Significant Decrease' not in x.value)
observations = observations - (tab.excel_ref('A1')
                               .expand(DOWN)
                               .filter(contains_string('Significant Change'))
                               .expand(RIGHT)
                              )
original_estimates = tab \
    .filter(contains_string('Original Estimates')) \
    .fill(DOWN) \
    .is_number()

observations = observations - original_estimates
savepreviewhtml([observations, original_estimates])
# -

CI = observations.shift(RIGHT)
Year = corner.fill(DOWN) & \
    observations.fill(LEFT)
Geography = corner.fill(DOWN).one_of(['United Kingdom', 'England and Wales'])
Age = corner.fill(RIGHT).is_not_blank()
Age_dim = HDim(Age, 'Age', CLOSEST, LEFT)
Age_dim.AddCellValueOverride('45-59/642', '45-59/64')
Age_dim.AddCellValueOverride('60/65 and over3', '60/65 and over')
Age_dim.AddCellValueOverride('All Ages', 'All ages')
Sex = corner.shift(DOWN).fill(RIGHT).is_not_blank()
Flow = corner.fill(DOWN).one_of(['Inflow', 'Outflow', 'Balance'])
csObs = ConversionSegment(observations, [
    HDim(Year,'Year', DIRECTLY, LEFT),
    HDim(Geography,'Geography', CLOSEST, ABOVE),
    Age_dim,
    HDim(Sex, 'Sex', CLOSEST, LEFT),
    HDim(Flow, 'Migration Flow', CLOSEST, ABOVE),
    HDimConst('Measure Type', 'Count'),
    HDimConst('Unit','People (thousands)'),
    HDim(CI,'CI',DIRECTLY,RIGHT),
])
savepreviewhtml(csObs)

tidy_revised = csObs.topandas()
tidy_revised

# Also need to pull out the group of original estimates

csRevs = ConversionSegment(original_estimates, [
    HDim(Year, 'Year', DIRECTLY, LEFT),
    HDim(Geography,'Geography', CLOSEST, ABOVE),
    Age_dim,
    HDim(Sex, 'Sex', CLOSEST, LEFT),
    HDim(Flow, 'Migration Flow', CLOSEST, ABOVE),
    HDimConst('Measure Type', 'Count'),
    HDimConst('Unit','People (thousands)'),
    HDim(original_estimates.shift(RIGHT), 'CI', DIRECTLY, RIGHT),
    HDimConst('Revision', 'Original Estimate')
])
savepreviewhtml(csRevs)

orig_estimates = csRevs.topandas()
orig_estimates

tidy = pd.concat([tidy_revised, orig_estimates], axis=0, join='outer', ignore_index=True, sort=False)
tidy

original_slice = tidy[tidy['Revision'] == 'Original Estimate']
tidy['Revision'] = tidy.apply(
    lambda row: '2011 Census Revision' if row['CI'] == ':' else 'Original Estimate',
    axis=1
)
tidy

# Check each observation has a year and use ints.

tidy['Year'] = tidy['Year'].apply(lambda x: pd.to_numeric(x, downcast='integer'))

# Ignore data markers for now and ensure all observations and confidence intervals are integers.
#
# **Todo: figure out what to do with data markers.**

import numpy as np
tidy['OBS'].replace('', np.nan, inplace=True)
tidy.dropna(subset=['OBS'], inplace=True)
if 'DATAMARKER' in tidy.columns:
    tidy.drop(columns=['DATAMARKER'], inplace=True)
tidy.rename(columns={'OBS': 'Value'}, inplace=True)
tidy['Value'] = tidy['Value'].astype(int)
tidy['CI'] = tidy['CI'].map(lambda x:
                            '' if x == ':' else int(x[:-2]) if x.endswith('.0') else 'ERR')
tidy

for col in tidy.columns:
    if col not in ['Value', 'Year', 'CI']:
        tidy[col] = tidy[col].astype('category')
        display(col)
        display(tidy[col].cat.categories)

# +
tidy['Geography'] = tidy['Geography'].cat.rename_categories({
    'United Kingdom': 'K02000001',
    'England and Wales': 'K04000001'
})
tidy['Age'] = tidy['Age'].cat.rename_categories({
    '15-24': 'agr/15-24',
    '25-44': 'agr/25-44',
    '45-59/64': 'agr/45-59-or-64',
    '60/65 and over': 'agr/60-or-65-and-over',
    'All ages': 'all',
    'Under 15': 'agr/under-15'
})
tidy['Sex'] = tidy['Sex'].cat.rename_categories({
    'Females': 'F',
    'Males': 'M',
    'Persons': 'T'
})
tidy['Migration Flow'].cat.categories = tidy['Migration Flow'].cat.categories.map(pathify)

tidy = tidy[['Geography', 'Year', 'Age', 'Sex', 'Migration Flow',
             'Value', 'Measure Type', 'Unit', 'CI', 'Revision']]
tidy

# +
from pathlib import Path
destinationFolder = Path('out')
destinationFolder.mkdir(exist_ok=True, parents=True)

tidy.to_csv(destinationFolder / ('observations.csv'), index = False)

# +
from gssutils.metadata import THEME

scraper.dataset.family = 'migration'
scraper.dataset.theme = THEME['population']
scraper.dataset.license = 'http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'

with open(destinationFolder / 'dataset.trig', 'wb') as metadata:
    metadata.write(scraper.generate_trig())
# -
csvw = CSVWMetadata('https://gss-cogs.github.io/ref_migration/')
csvw.create(destinationFolder / 'observations.csv', destinationFolder / 'observations.csv-schema.json')

