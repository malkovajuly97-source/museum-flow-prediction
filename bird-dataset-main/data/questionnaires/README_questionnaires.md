# Data description of questionnaires


Question| Variable name| Possible values|
|:--------------------------------------------:|:----------:|:----------:|
/| passationBeforeVisit | timestamp |
What is your participant number? | visitor_id | string |
What is your age?| age | integer |
You are...| gender | woman/man/non_binary |
What is your city (and country) of residence?| city_country_residence | string |
What is your nationality? | nationality |string |
What is your level in French?| french_level | Do not know/Basic/Intermediary/Advanced/Native-bilingual|
What is the highest degree you have obtained?| diploma | Master's Degree/A levels/PhD/BA, BS-BSc/BTEXX Higher National Diploma|
In general, you go to a museum for interest in a particular type of exhibits.| one_artwork_interest | from 1 (did not come for one specific artwork) to 5 (did come for a specific artwork)|
In general, you go to a museum to discover as many exhibits as possible.| discovery_interest | from 1 (do not want to discover) to 5 (want to discover)|
You are tolerant to the crowd in a museum. | crowd_tolerance | from 1 (intolerant) to 5 (tolerant)|
To avoid the crowd, you would be ready to give up seeing an exhibit that you were particularly interested in.| lose_interest_with_crowd | from 1 (give up an exhibit because of the crowd) to 5 (do not care)|
You are tolerant to the distance to go in a museum.| distance_tolerance | from 1 (intolerant) to 5 (tolerant)|
Have you ever visited the museum of fine arts of Nancy?| already_visited | Yes or No|
If so, how many times?| number_visits | integer|
If so, when was your last visit?|last_time_visited| never/Several years ago/About a year ago/Several months ago/A few weeks ago|
Today, are you visiting this museum alone or in a group?| group_or_alone | group/alone|
What motivates your visit today?| 'motiv_curiosity'/'motiv_else'/'motiv_familyOut'/'motiv_price'/'motiv_schoolOut'/'motiv_weather'| 1(has this motivation)/0 (does not have this motivation)|
What are your visit objectives?|'visitGoal_surprised'/ 'visitGoal_else'/'visitGoal_explore'/ 'visitGoal_inspiration'/ 'visitGoal_fun'/'visitGoal_interact'/ 'visitGoal_learn'/ 'visitGoal_noGoal'/'visitGoal_SeeAgain'/ 'visitGoal_mindOff'| 1(has the goal)/0(does not have the goal)|
Do you set a maximum duration for this visit? (if yes, specify the duration in minutes)| visit_duration | unlimited/60/90/120/45/30/10|
Do you have an eye problem? | eye_problem | Normal vision/Normal vision with visual correction device (glasses, lenses)/Daltonism/Amblyopia|
You feel physically tired | physical_sleepiness| from 1 (strongly disagree) to 5 (strongly agree)|
You feel mentally tired | mental_sleepiness | from 1 (strongly disagree) to 5 (strongly agree)|
In general, how would you rate your traveling speed? | speed | from 1 (slow) to 5 (fast)|
What is your current mood? | current_emotion | from 1 (bad mood) to 5 (good mood)|
/ | passationAfterVisit | timestamp|
What is your level of knowledge in art?| art_knowledge | No knowledge/Low level/General level/Art lover/ Specialist-expert|
What is your level of involvement in art? | art_involvement | No involvement/Art student/ Art teacher/ Professional-artist|
Which type(s) of museums do you usually visit? | musHabit_archeo/musHabit_histArt/ musHabit_castle/ musHabit_contemporary/musHabit_else/ musHabit_fineArt/ musHabit_natHist/musHabit_nature/ musHabit_none| 1 (if they usually visit) or 0|
How often do you visit museums? | visit_rate | a few times a year/ rarely or never/ One or more times a month|
How do you discover new exhibitions and collections? | musDisco_else/musDisco_familyFriends/ musDisco_magazine/ musDisco_media/musDisco_nothing/ musDisco_socNetwork/| 1 (is they discover through this modality) or 0|
Do you often take an audioguide when you visit a museum? | taking_audioguide| No/Yes
If a museum offered it to you, would you agree to install an application on your smartphone to improve your visit experience?|application_interest | Yes/No|
If so, what would be the interesting features for you?|wantedFunc_catalog/wantedFunc_else/ wantedFunc_games/ wantedFunc_map/wantedFunc_nothing/ wantedFunc_reco/ wantedFunc_thematicTour| 1 (if they want the functionnality) or 0|
Do you know the mobile application of the Nancy Museum of Fine Arts? | appli_knowledge | No/Yes but I did not use it during the visit|
Overall, you are satisfied at the end of the visit.| satisfaction | from 1 (strongly disagree) to 5 (strongly agree)|
You have reached your goals of visit. | goals_reached | from 1 (strongly disagree) to 5 (strongly agree)|
You have been bothered by the eye-tracking glasses during your visit.| device_trouble | from 1 (strongly disagree) to 5 (strongly agree)|
You were embarrassed by the crowd during your visit. | crowd_trouble | from 1 (strongly disagree) to 5 (strongly agree)|
You had the impression of traveling a great distance in the museum.| dist_sensation |from 1 (strongly disagree) to 5 (strongly agree)|
If it was possible to have path recommendations in the museum, you would like to have the choice among several pathes.| multiple_paths | from 1 (they do not want several paths) to 5 (they want several paths)|
If it was possible to have path recommendations in the museum, you would like to choose the frequency of the notifications and/or the number of recommendations (path length).| recsys_personalization | from 1 (strongly disagree) to 5 (strongly agree) |
If it were possible to have path recommendations in the museum, you would like to have diverse recommendations.| diversity| from 1 (strongly disagree) to 5 (strongly agree)|
If it were possible to have path recommendations in the museum, you would like a coherent thematic path.|theme_path|  from 1 (strongly disagree) to 5 (strongly agree)|
If it were possible to have path recommendations in the museum, you would agree to be geolocated in the museum.|geolocalisation_acceptance| from 1 (strongly disagree) to 5 (strongly agree)|
The exhibits you want to see during your visits to the Nancy Museum of Fine Arts are dependent on the context (time of year, people who accompany you, etc.).| context_dependence |  from 1 (strongly disagree) to 5 (strongly agree)|
The exhibits you want to see during your visits to the Nancy Museum of Fine Arts are dependent on your mood. |mood_dependence| from 1 (strongly disagree) to 5 (strongly agree)|
The exhibits you want to see during your visits to the Nancy Museum of Fine Arts are dependent on your state of tiredness.| sleepiness_dependence| from 1 (strongly disagree) to 5 (strongly agree)|
You feel physically tired at the end of the visit. | end_visit_physical_sleepiness| from 1 (strongly disagree) to 5 (strongly agree)|
You feel mentally tired at the end of the visit. | end_visit_mental_sleepiness | from 1 (strongly disagree) to 5 (strongly agree)|
You have read and learned something from the plates with the description of the exhibits. | panel_interest | 0=unread plates, 1=strongly disagree, 5=strongly agree|
Can you name something you learned or remembered during your visit? | memory_test_fr/memory_test_en | string|
Can you name something that surprised you during your visit? | surprise_event_fr/surprise_event_en | string |
Do you have additional remarks?| comments_fr/comments_en | string |