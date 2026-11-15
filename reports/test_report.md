# Field Shift — test report (final, v2.0.1)

Build sandbox: Python 3.13.18 on Linux · 2026-11-14
**Sandbox result:** 154 passed, 1 skipped in 87.19s (0:01:27)
**Mac result (Python 3.14, Streamlit 1.67, 14 Nov 2026):** 152 passed before Phase 5 (incl. all 8 app tests); Final v2.0.0 on the Mac: 161 passed, 1 failed (docs test: Random Forest MAE 11.3 on macOS vs 11.24 on Linux). v2.0.1 documents both values and allows a ±0.1 cross-platform tolerance — re-run on the Mac expected: 162 passed.

| Test file | Passed | Skipped | Failed |
|---|---|---|---|
| `tests/test_app.py` (8 tests, module skipped: no Streamlit in sandbox) | 0 | 8 | 0 |
| `tests/test_analysis.py` | 6 | 0 | 0 |
| `tests/test_data_units.py` | 11 | 0 | 0 |
| `tests/test_docs_consistency.py` | 5 | 0 | 0 |
| `tests/test_drought_counterfactual.py` | 35 | 0 | 0 |
| `tests/test_engine.py` | 7 | 0 | 0 |
| `tests/test_feasibility.py` | 9 | 0 | 0 |
| `tests/test_input_validation.py` | 14 | 0 | 0 |
| `tests/test_missing_data.py` | 4 | 0 | 0 |
| `tests/test_ml_leakage.py` | 6 | 0 | 0 |
| `tests/test_parameter_registry.py` | 3 | 0 | 0 |
| `tests/test_processing.py` | 10 | 0 | 0 |
| `tests/test_reproducibility.py` | 5 | 0 | 0 |
| `tests/test_scenario_provenance.py` | 6 | 0 | 0 |
| `tests/test_soil_sensitivity.py` | 7 | 0 | 0 |
| `tests/test_water_balance.py` | 26 | 0 | 0 |

Skipped: `tests/test_app.py` (8 Streamlit AppTest tests) — Streamlit is not installed in the build sandbox; they run on the Mac.
No expected failures (xfail) remain; the retired drought rule is documented in `docs/AUDIT_LOG.md`.

Full list:
```
PASSED tests/test_analysis.py::test_theil_sen_recovers_known_slope
PASSED tests/test_analysis.py::test_theil_sen_no_trend_in_noise
PASSED tests/test_analysis.py::test_trends_table_reports_significance
PASSED tests/test_analysis.py::test_regimes_cover_every_season
PASSED tests/test_analysis.py::test_yield_model_beats_baseline
PASSED tests/test_analysis.py::test_what_if_is_monotonic
PASSED tests/test_data_units.py::test_real_data_passes
PASSED tests/test_data_units.py::test_rain_in_inches_is_rejected
PASSED tests/test_data_units.py::test_both_rain_products_in_inches_rejected
PASSED tests/test_data_units.py::test_temperature_in_fahrenheit_rejected
PASSED tests/test_data_units.py::test_wrong_declared_unit_rejected
PASSED tests/test_data_units.py::test_power_for_another_location_rejected
PASSED tests/test_data_units.py::test_unscaled_ndvi_rejected
PASSED tests/test_data_units.py::test_lst_in_celsius_rejected
PASSED tests/test_data_units.py::test_yield_in_tonnes_per_hectare_rejected
PASSED tests/test_data_units.py::test_soil_texture_not_summing_to_100_rejected
PASSED tests/test_data_units.py::test_pipeline_stops_before_processing_on_bad_units
PASSED tests/test_docs_consistency.py::test_no_out_of_date_banners_left
PASSED tests/test_docs_consistency.py::test_yield_model_numbers
PASSED tests/test_docs_consistency.py::test_water_balance_numbers
PASSED tests/test_docs_consistency.py::test_sensitivity_and_default_recommendation_numbers
PASSED tests/test_docs_consistency.py::test_rotation_count_and_market_potential_language
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[current_corn_soy-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[current_corn_soy-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[current_corn_soy-0.3]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_covers-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_covers-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_covers-0.3]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_rye-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_rye-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_rye-0.3]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[sorghum_soy_vetch-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[sorghum_soy_vetch-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[sorghum_soy_vetch-0.3]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[sorghum_soy_wheat_dc-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[sorghum_soy_wheat_dc-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[sorghum_soy_wheat_dc-0.3]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_wheat_vetch-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_wheat_vetch-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[corn_soy_wheat_vetch-0.3]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[alfalfa_corn_soy-0.8]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[alfalfa_corn_soy-0.5]
PASSED tests/test_drought_counterfactual.py::test_less_rain_never_improves_modelled_water_supply_for_the_same_rotation[alfalfa_corn_soy-0.3]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_covers-current_corn_soy-1.0]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_covers-current_corn_soy-0.8]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_covers-current_corn_soy-0.5]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_covers-current_corn_soy-0.3]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_rye-current_corn_soy-1.0]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_rye-current_corn_soy-0.8]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_rye-current_corn_soy-0.5]
PASSED tests/test_drought_counterfactual.py::test_adding_a_cover_crop_never_reduces_the_modelled_deficit[corn_soy_rye-current_corn_soy-0.3]
PASSED tests/test_drought_counterfactual.py::test_regression_alfalfa_does_not_rise_when_rain_is_halved
PASSED tests/test_drought_counterfactual.py::test_no_saturation_rotations_with_different_crops_stay_distinct[0.8]
PASSED tests/test_drought_counterfactual.py::test_no_saturation_rotations_with_different_crops_stay_distinct[0.5]
PASSED tests/test_drought_counterfactual.py::test_no_saturation_rotations_with_different_crops_stay_distinct[0.3]
PASSED tests/test_drought_counterfactual.py::test_water_score_order_changes_are_explained_by_modelled_shortfall
PASSED tests/test_drought_counterfactual.py::test_engine_states_water_model_limitation
PASSED tests/test_engine.py::test_three_strategies_with_all_fields
PASSED tests/test_engine.py::test_priorities_change_the_ranking
PASSED tests/test_engine.py::test_covers_reduce_bare_soil
PASSED tests/test_engine.py::test_forage_outlet_raises_alfalfa_market_potential
PASSED tests/test_engine.py::test_deprecated_income_key_still_accepted
PASSED tests/test_engine.py::test_month_list_wraps_year
PASSED tests/test_engine.py::test_near_tie_flagged_for_default_pair
PASSED tests/test_feasibility.py::test_vetch_after_soybean_needs_interseeding
PASSED tests/test_feasibility.py::test_vetch_after_wheat_and_rye_after_corn_are_fine
PASSED tests/test_feasibility.py::test_low_ph_is_conditional_not_excluded
PASSED tests/test_feasibility.py::test_good_soil_clears_alfalfa_soil_checks
PASSED tests/test_feasibility.py::test_alfalfa_without_forage_outlet_is_flagged
PASSED tests/test_feasibility.py::test_infeasible_rotation_never_shown_as_alternative
PASSED tests/test_feasibility.py::test_current_rotation_always_shown_first
PASSED tests/test_feasibility.py::test_water_limit_excludes_thirstier_rotations
PASSED tests/test_feasibility.py::test_fewer_than_two_alternatives_gives_notice
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad0]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad1]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad2]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad3]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad4]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad5]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad6]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad7]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad8]
PASSED tests/test_input_validation.py::test_invalid_priorities_rejected[bad9]
PASSED tests/test_input_validation.py::test_valid_priorities_give_scores_in_range
PASSED tests/test_input_validation.py::test_invalid_constraints_rejected[bad0]
PASSED tests/test_input_validation.py::test_invalid_constraints_rejected[bad1]
PASSED tests/test_input_validation.py::test_invalid_constraints_rejected[bad2]
PASSED tests/test_missing_data.py::test_pipeline_runs_without_optional_datasets[smap_only]
PASSED tests/test_missing_data.py::test_pipeline_runs_without_optional_datasets[all_optional]
PASSED tests/test_missing_data.py::test_pipeline_stops_with_clear_error_without_required_dataset
PASSED tests/test_missing_data.py::test_stale_data_is_reported
PASSED tests/test_ml_leakage.py::test_held_out_yield_does_not_enter_detrending[2008]
PASSED tests/test_ml_leakage.py::test_held_out_yield_does_not_enter_detrending[2012]
PASSED tests/test_ml_leakage.py::test_held_out_yield_does_not_enter_detrending[2023]
PASSED tests/test_ml_leakage.py::test_held_out_yield_does_not_change_its_prediction
PASSED tests/test_ml_leakage.py::test_saved_out_of_sample_predictions_reproduce_metrics
PASSED tests/test_ml_leakage.py::test_model_of_record_beats_baseline_out_of_sample
PASSED tests/test_parameter_registry.py::test_registry_is_current_and_complete
PASSED tests/test_parameter_registry.py::test_literature_ranges_respected_or_flagged
PASSED tests/test_parameter_registry.py::test_assumptions_are_not_labelled_as_literature
PASSED tests/test_processing.py::test_extraterrestrial_radiation_matches_fao56_example
PASSED tests/test_processing.py::test_hargreaves_et0_is_physical
PASSED tests/test_processing.py::test_power_daily_complete
PASSED tests/test_processing.py::test_smap_quality_filter
PASSED tests/test_processing.py::test_modis_quality_filter
PASSED tests/test_processing.py::test_ecostress_filters
PASSED tests/test_processing.py::test_master_table
PASSED tests/test_processing.py::test_hargreaves_never_negative_in_extreme_cold
PASSED tests/test_processing.py::test_footprint_table_covers_every_dataset
PASSED tests/test_processing.py::test_modis_assigned_to_composite_midpoint
PASSED tests/test_reproducibility.py::test_manifest_checksums_match_raw_files
PASSED tests/test_reproducibility.py::test_manifest_detects_a_changed_file
PASSED tests/test_reproducibility.py::test_engine_is_deterministic
PASSED tests/test_reproducibility.py::test_yield_model_predictions_reproducible
PASSED tests/test_reproducibility.py::test_sensitivity_script_same_seed_same_output
PASSED tests/test_scenario_provenance.py::test_every_crop_loss_has_a_known_provenance
PASSED tests/test_scenario_provenance.py::test_only_corn_soybean_sorghum_are_rf_estimates
PASSED tests/test_scenario_provenance.py::test_2012_reports_observed_held_out_and_full_sample_separately
PASSED tests/test_scenario_provenance.py::test_scenarios_are_labelled_in_sample
PASSED tests/test_scenario_provenance.py::test_what_if_flags_extrapolation
PASSED tests/test_scenario_provenance.py::test_random_forest_not_used_in_scoring
PASSED tests/test_soil_sensitivity.py::test_scores_differ_between_sandy_and_clay
PASSED tests/test_soil_sensitivity.py::test_low_storage_sand_has_more_water_stress
PASSED tests/test_soil_sensitivity.py::test_wet_soil_tolerance_only_matters_on_slow_drainage
PASSED tests/test_soil_sensitivity.py::test_low_organic_matter_raises_soil_health_relevance
PASSED tests/test_soil_sensitivity.py::test_acidic_soil_flags_alfalfa_conditional_not_excluded
PASSED tests/test_soil_sensitivity.py::test_free_draining_soil_clears_alfalfa_drainage_warning
PASSED tests/test_soil_sensitivity.py::test_missing_soil_measurements_are_reported_not_invented
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[current_corn_soy]
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[corn_soy_covers]
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[corn_soy_rye]
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[sorghum_soy_vetch]
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[sorghum_soy_wheat_dc]
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[corn_soy_wheat_vetch]
PASSED tests/test_water_balance.py::test_water_is_conserved_and_storage_bounded[alfalfa_corn_soy]
PASSED tests/test_water_balance.py::test_no_rain_dries_the_soil_and_stresses_crops
PASSED tests/test_water_balance.py::test_saturating_rain_removes_stress
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[current_corn_soy]
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[corn_soy_covers]
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[corn_soy_rye]
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[sorghum_soy_vetch]
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[sorghum_soy_wheat_dc]
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[corn_soy_wheat_vetch]
PASSED tests/test_water_balance.py::test_less_rain_more_shortfall_more_heat_more_shortfall[alfalfa_corn_soy]
PASSED tests/test_water_balance.py::test_more_storage_less_stress
PASSED tests/test_water_balance.py::test_relative_yield_bounded_and_uses_fao33_ky
PASSED tests/test_water_balance.py::test_claypan_rooting_limit_inferred_from_ssurgo
PASSED tests/test_water_balance.py::test_winter_wheat_sown_the_autumn_before_harvest
PASSED tests/test_water_balance.py::test_hargreaves_et0_close_to_penman_monteith
PASSED tests/test_water_balance.py::test_experimental_runoff_conserves_water[HSG C, good condition]
PASSED tests/test_water_balance.py::test_experimental_runoff_conserves_water[HSG D, good condition]
PASSED tests/test_water_balance.py::test_experimental_runoff_conserves_water[HSG D, poor condition]
PASSED tests/test_water_balance.py::test_scs_runoff_matches_curve_number_equation
PASSED tests/test_water_balance.py::test_production_scoring_has_no_runoff
SKIPPED [1] tests/test_app.py:9: could not import 'streamlit.testing.v1': No module named 'streamlit'
```