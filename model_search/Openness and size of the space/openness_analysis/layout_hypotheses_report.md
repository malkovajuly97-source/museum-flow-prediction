# Layout hypotheses: correlation with movement

| Feature | speed | duration | nb_stops | nb_items | stop_intensity |
|---------|-------|----------|----------|----------|----------------|
| H2_min_width | -0.037 | 0.092 | 0.138 | 0.217 | 0.094 |
| H2_pct_narrow | -0.047 | -0.098 | 0.010 | -0.142 | 0.177 |
| H3_mean_connectivity | -0.112 | 0.163 | 0.240 | 0.249 | 0.260 |
| H3_pct_low_connectivity | -0.302 | 0.179 | 0.104 | -0.272 | -0.073 |
| H4_mean_depth | -0.243 | 0.167 | 0.193 | 0.121 | 0.133 |
| H4_max_depth | -0.020 | 0.210 | 0.107 | 0.154 | -0.084 |
| H5_pct_corridor | -0.055 | 0.048 | 0.012 | 0.164 | -0.001 |
| H5_mean_aspect_ratio | -0.132 | 0.123 | 0.070 | 0.226 | 0.014 |
| H6_mean_exhibit_density | 0.258 | -0.114 | 0.019 | 0.289 | 0.148 |
| H7_pct_start | 0.197 | -0.158 | -0.223 | -0.097 | -0.193 |
| H7_pct_mid | -0.153 | 0.038 | -0.080 | -0.257 | -0.174 |
| H7_pct_end | -0.099 | 0.117 | 0.225 | 0.197 | 0.242 |
| H7_mean_t_norm | -0.148 | 0.145 | 0.229 | 0.158 | 0.215 |
| H8_n_returns | 0.037 | 0.219 | 0.020 | 0.112 | -0.296 |
| H8_pct_path_revisit | -0.327 | 0.325 | 0.259 | 0.169 | 0.115 |
| H9_width_std | -0.021 | -0.113 | -0.076 | -0.257 | 0.003 |
| H9_width_range | -0.205 | 0.200 | 0.128 | -0.035 | -0.065 |
| H10_mean_dist_to_exit | 0.065 | 0.119 | 0.064 | 0.205 | -0.090 |
| H10_mean_path_remaining | -0.026 | 0.271 | 0.152 | 0.138 | -0.110 |
| H11_mean_dist_to_staircase | 0.176 | -0.172 | -0.015 | -0.085 | 0.271 |
| H11_min_dist_to_staircase | -0.400 | 0.249 | 0.204 | -0.077 | 0.058 |
| H11_pct_near_staircase | -0.045 | -0.062 | 0.037 | 0.085 | 0.169 |
| H12_n_turns | -0.154 | 0.375 | 0.317 | 0.237 | 0.069 |
| H12_turns_per_length | -0.118 | 0.195 | 0.253 | 0.185 | 0.253 |
| H12_turns_per_minute | 0.432 | -0.490 | -0.443 | -0.288 | -0.055 |

## Strongest effects (|r| > 0.25)

- **H12_turns_per_minute** vs **duration**: r = -0.490
- **H12_turns_per_minute** vs **nb_stops**: r = -0.443
- **H12_turns_per_minute** vs **speed**: r = 0.432
- **H11_min_dist_to_staircase** vs **speed**: r = -0.400
- **H12_n_turns** vs **duration**: r = 0.375
- **H8_pct_path_revisit** vs **speed**: r = -0.327
- **H8_pct_path_revisit** vs **duration**: r = 0.325
- **H12_n_turns** vs **nb_stops**: r = 0.317
- **H3_pct_low_connectivity** vs **speed**: r = -0.302
- **H8_n_returns** vs **stop_intensity**: r = -0.296
- **H6_mean_exhibit_density** vs **nb_items**: r = 0.289
- **H12_turns_per_minute** vs **nb_items**: r = -0.288
- **H3_pct_low_connectivity** vs **nb_items**: r = -0.272
- **H10_mean_path_remaining** vs **duration**: r = 0.271
- **H11_mean_dist_to_staircase** vs **stop_intensity**: r = 0.271
- **H3_mean_connectivity** vs **stop_intensity**: r = 0.260
- **H8_pct_path_revisit** vs **nb_stops**: r = 0.259
- **H6_mean_exhibit_density** vs **speed**: r = 0.258
- **H9_width_std** vs **nb_items**: r = -0.257
- **H7_pct_mid** vs **nb_items**: r = -0.257
- **H12_turns_per_length** vs **stop_intensity**: r = 0.253
- **H12_turns_per_length** vs **nb_stops**: r = 0.253

## Summary of 12 layout hypotheses

1. **H1 Width** (already in openness): passage_width_mean — narrower paths: more stops, lower speed.
2. **H2 Bottlenecks**: min_width, pct_narrow — weak; more narrow points slightly link to fewer items (r~-0.14), more stop_intensity (r~0.18).
3. **H3 Connectivity**: mean_connectivity, pct_low_connectivity — **strong**: more path in low-connectivity (dead-end) zones → lower speed (r~-0.30), fewer items (r~-0.27); higher connectivity → more stops and stop_intensity (r~0.26).
4. **H4 Depth**: mean_depth — deeper paths (from entrance) → lower speed (r~-0.24), more stops (r~0.19).
5. **H5 Corridor vs hall**: pct_corridor, mean_aspect_ratio — weak; higher aspect (more corridor-like) → fewer items (r~-0.23).
6. **H6 Exhibit density**: mean_exhibit_density — **strong**: higher density along path → higher speed (r~0.26), more items (r~0.29).
7. **H7 Order**: pct_start/mid/end, mean_t_norm — more time in start phase → higher speed, fewer stops; more in end → more stops (r~0.24), higher stop_intensity (r~0.24).
8. **H8 Returns**: n_returns, pct_path_revisit — **strong**: more revisit → lower speed (r~-0.33), longer duration (r~0.33), more stops (r~0.26); n_returns vs stop_intensity r~-0.30.
9. **H9 Width variance**: width_std, width_range — more variance → fewer items (r~-0.26); width_range → lower speed (r~-0.21), longer duration (r~0.20).
10. **H10 Exit proximity**: mean_path_remaining — more path remaining (further from exit) → longer duration (r~0.27), more items (r~0.20).
11. **H11 Staircase proximity**: mean_dist_to_staircase, min_dist_to_staircase, pct_near_staircase — proximity to staircases (zones 1, 2, 5 and between 12–13); see correlations in table above.
12. **H12 Turn count**: n_turns, turns_per_length, turns_per_minute — number of turns (direction change > 30 deg) along path; see correlations in table above.