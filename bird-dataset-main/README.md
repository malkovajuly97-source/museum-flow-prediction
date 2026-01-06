# BIRD dataset

## Description

Behavioral and Identity-Related Dataset (BIRD) is a museum dataset for indoor environment analysis in the context of cultural heritage. It was collected in 2019 at the Nancy Museum of Fine Arts and contain currently 51 visitors.
This dataset can be employed for multiple objectives: trajectory prediction, behavior analysis, recommendation, natural language processing, crowd simulation...
For more detailed information about BIRD, please refer to the following paper: Alexanne Worm, Florian Marchal, and Sylvain Castagnos. 2025. BIRD: A
Museum Open Dataset Combining Behavior Patterns and Identity Types to Better Model Visitors’ Experience. In Adjunct Proceedings of the 33rd ACM Conference on User Modeling, Adaptation and Personalization (UMAP Adjunct’25), June 16–19, 2025, New York City, NY, USA. ACM, New York, NY, USA, 5 pages. https://doi.org/10.1145/3708319.3733686

## Installation

To run the code in the folder [code_dataset](code_dataset/), you can install the libraries with pip: pip install -r requirements.txt
This code contains examples to normalize raw trajectories, cluster data and observe some statistics. 

## Usage

Visitors are represented by a unique id that can be found in each file name or content (12 numbers). A visitor's profile contains these information: a trajectory with their semantic information, the list of artworks seen (observation start and end, in two files respectively), explicit feedback and responses to questionnaires.

This dataset contain the following folders and files:
- [raw_trajectories](data/raw_trajectories/): raw trajectories (without any further treatment) in CSV format.
- [normalized_trajectories](data/normalized_trajectories/): normalized trajectories obtained with MovingPandas (position interpolation every two seconds) in CSV format.
- [start_obs_artworks](data/start_obs_artworks/): list of artworks seen in CSV format. Each timestamp corresponds to the start of observation. 
- [end_obs_artworks](data/end_obs_artworks/): list of artworks seen in CSV format. Each timestamp corresponds to the end of observation.
- [questionnaires](data/questionnaires/): post and pre questionnaires given to the visitor at the end and beginning of the visit. A Readme is also available to understand the files and their items. 
- artworks_dataset (CSV format): list of artworks that can be seen by the visitor during their visit. This file contains information about each artwork (description, author...).
- explicit_feedback_visitors: artworks liked by visitors (that could have been observed during the visit or not).
- NMFA_3floors_plan (JSON format): Nancy Museum of Fine Arts plan.
- museum_walls_plan (PDF): Nancy Museum of Fine Arts plan with walls name.
- semantic_info_entire_trajectories: information about each trajectory (duration, mean speed...).
- museum_attendance (CSV format): number of visitors of the museum between May 2018 and June 2019.
- post_questionnaire (PDF): questionnaire given at end of visit (with all items).
- pre_questionnaire (PDF): questionnaire given at the beginning of visit (with all items).


## Roadmap
More data will soon be added in this repository:
- Gaze data
- More visitors 
- Behavioral and identity-related data: isovists, artwork complexity...
- Code with some examples of the dataset use, and statistical results

## Authors and acknowledgment
This research was supported by the non-economic valuation project called MBANv2. It was the subject of an agreement signed by the University of Lorraine, the Urban Community of Greater Nancy and the Nancy Museum of Fine Arts. We would like to thank Sophie Mouton, Sophie Toulouze, Charles Villeneuve de Janti, Michèle Leinen, and Jean-Paul Darada for providing information on the artworks and for authorizing this study to be conducted within the museum.

## License
This dataset is under the CC BY-NC-SA 4.0 license (for more information, please refer to the official website:  https://creativecommons.org/licenses/by-nc-sa/4.0/). If you find this dataset useful for your research, then please cite: Alexanne Worm, Florian Marchal, and Sylvain Castagnos. 2025. BIRD: A
Museum Open Dataset Combining Behavior Patterns and Identity Types to Better Model Visitors’ Experience. In Adjunct Proceedings of the 33rd ACM Conference on User Modeling, Adaptation and Personalization (UMAP Adjunct’25), June 16–19, 2025, New York City, NY, USA. ACM, New York, NY, USA, 5 pages. https://doi.org/10.1145/3708319.3733686

## Project status
This dataset is currently under extension. More trajectories and specific information will soon be added to the repository. 51 trajectories are officially available.
