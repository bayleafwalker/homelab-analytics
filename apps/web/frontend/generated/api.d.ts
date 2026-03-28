export interface paths {
    "/api/categories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Categories */
        get: operations["list_categories_api_categories_get"];
        put?: never;
        /** Create Category */
        post: operations["create_category_api_categories_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Actions */
        get: operations["get_actions_api_ha_actions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/actions/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Action Proposals */
        get: operations["get_action_proposals_api_ha_actions_proposals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/actions/proposals/{action_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Action Proposal */
        get: operations["get_action_proposal_api_ha_actions_proposals__action_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/actions/proposals/{action_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve Action Proposal */
        post: operations["approve_action_proposal_api_ha_actions_proposals__action_id__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/actions/proposals/{action_id}/dismiss": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Dismiss Action Proposal */
        post: operations["dismiss_action_proposal_api_ha_actions_proposals__action_id__dismiss_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/actions/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Actions Status */
        get: operations["get_actions_status_api_ha_actions_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/bridge/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Bridge Status */
        get: operations["get_bridge_status_api_ha_bridge_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/entities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Ha Entities */
        get: operations["get_ha_entities_api_ha_entities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/entities/{entity_id}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Ha Entity History */
        get: operations["get_ha_entity_history_api_ha_entities__entity_id__history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/ingest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Ha States */
        post: operations["ingest_ha_states_api_ha_ingest_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/mqtt/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Mqtt Status */
        get: operations["get_mqtt_status_api_ha_mqtt_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/policies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Policies */
        get: operations["get_policies_api_ha_policies_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ha/policies/evaluate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Evaluate Policies */
        post: operations["evaluate_policies_api_ha_policies_evaluate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/homelab/backups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Backup Freshness */
        get: operations["get_backup_freshness_api_homelab_backups_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/homelab/services": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Service Health */
        get: operations["get_service_health_api_homelab_services_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/homelab/storage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Storage Risk */
        get: operations["get_storage_risk_api_homelab_storage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/homelab/workloads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Workload Cost 7D */
        get: operations["get_workload_cost_7d_api_homelab_workloads_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Scenarios Route */
        get: operations["list_scenarios_route_api_scenarios_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/expense-shock": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Expense Shock */
        post: operations["create_expense_shock_api_scenarios_expense_shock_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/income-change": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Income Change */
        post: operations["create_income_change_api_scenarios_income_change_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/loan-what-if": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Loan What If */
        post: operations["create_loan_what_if_api_scenarios_loan_what_if_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/tariff-shock": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Tariff Shock */
        post: operations["create_tariff_shock_api_scenarios_tariff_shock_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/{scenario_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Scenario Metadata */
        get: operations["get_scenario_metadata_api_scenarios__scenario_id__get"];
        put?: never;
        post?: never;
        /** Archive Scenario */
        delete: operations["archive_scenario_api_scenarios__scenario_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/{scenario_id}/assumptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Scenario Assumptions */
        get: operations["get_scenario_assumptions_api_scenarios__scenario_id__assumptions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/{scenario_id}/cashflow": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Income Scenario Cashflow */
        get: operations["get_income_scenario_cashflow_api_scenarios__scenario_id__cashflow_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scenarios/{scenario_id}/comparison": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Scenario Comparison */
        get: operations["get_scenario_comparison_api_scenarios__scenario_id__comparison_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Oidc Callback */
        get: operations["oidc_callback_auth_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Start Oidc Login */
        get: operations["start_oidc_login_auth_login_get"];
        put?: never;
        /** Login */
        post: operations["login_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Auth Me */
        get: operations["auth_me_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/service-tokens": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Service Tokens */
        get: operations["list_service_tokens_auth_service_tokens_get"];
        put?: never;
        /** Create Service Token Endpoint */
        post: operations["create_service_token_endpoint_auth_service_tokens_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/service-tokens/{token_id}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke Service Token Endpoint */
        post: operations["revoke_service_token_endpoint_auth_service_tokens__token_id__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Auth Users */
        get: operations["list_auth_users_auth_users_get"];
        put?: never;
        /** Create Auth User */
        post: operations["create_auth_user_auth_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Auth User */
        patch: operations["update_auth_user_auth_users__user_id__patch"];
        trace?: never;
    };
    "/auth/users/{user_id}/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reset Auth User Password */
        post: operations["reset_auth_user_password_auth_users__user_id__password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories/overrides": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Category Overrides */
        get: operations["get_category_overrides_categories_overrides_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories/overrides/{counterparty_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Category Override Endpoint */
        put: operations["set_category_override_endpoint_categories_overrides__counterparty_name__put"];
        post?: never;
        /** Delete Category Override */
        delete: operations["delete_category_override_categories_overrides__counterparty_name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories/rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Category Rules */
        get: operations["get_category_rules_categories_rules_get"];
        put?: never;
        /** Create Category Rule */
        post: operations["create_category_rule_categories_rules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/categories/rules/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Category Rule */
        delete: operations["delete_category_rule_categories_rules__rule_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/column-mappings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Column Mappings */
        get: operations["list_column_mappings_config_column_mappings_get"];
        put?: never;
        /** Create Column Mapping */
        post: operations["create_column_mapping_config_column_mappings_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/column-mappings/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Column Mapping */
        post: operations["preview_column_mapping_config_column_mappings_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/column-mappings/{column_mapping_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Column Mapping */
        get: operations["get_column_mapping_config_column_mappings__column_mapping_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/column-mappings/{column_mapping_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Column Mapping Archived State */
        patch: operations["set_column_mapping_archived_state_config_column_mappings__column_mapping_id__archive_patch"];
        trace?: never;
    };
    "/config/column-mappings/{column_mapping_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Column Mapping Diff */
        get: operations["get_column_mapping_diff_config_column_mappings__column_mapping_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/dataset-contracts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Dataset Contracts */
        get: operations["list_dataset_contracts_config_dataset_contracts_get"];
        put?: never;
        /** Create Dataset Contract */
        post: operations["create_dataset_contract_config_dataset_contracts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/dataset-contracts/{dataset_contract_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Dataset Contract */
        get: operations["get_dataset_contract_config_dataset_contracts__dataset_contract_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/dataset-contracts/{dataset_contract_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Dataset Contract Archived State */
        patch: operations["set_dataset_contract_archived_state_config_dataset_contracts__dataset_contract_id__archive_patch"];
        trace?: never;
    };
    "/config/dataset-contracts/{dataset_contract_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Dataset Contract Diff */
        get: operations["get_dataset_contract_diff_config_dataset_contracts__dataset_contract_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/execution-schedules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Execution Schedules */
        get: operations["list_execution_schedules_config_execution_schedules_get"];
        put?: never;
        /** Create Execution Schedule */
        post: operations["create_execution_schedule_config_execution_schedules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/execution-schedules/{schedule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Execution Schedule */
        delete: operations["delete_execution_schedule_config_execution_schedules__schedule_id__delete"];
        options?: never;
        head?: never;
        /** Update Execution Schedule */
        patch: operations["update_execution_schedule_config_execution_schedules__schedule_id__patch"];
        trace?: never;
    };
    "/config/execution-schedules/{schedule_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Execution Schedule Archived State */
        patch: operations["set_execution_schedule_archived_state_config_execution_schedules__schedule_id__archive_patch"];
        trace?: never;
    };
    "/config/extension-registry-activations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Extension Registry Activations */
        get: operations["list_extension_registry_activations_config_extension_registry_activations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/extension-registry-revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Extension Registry Revisions */
        get: operations["list_extension_registry_revisions_config_extension_registry_revisions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/extension-registry-revisions/{extension_registry_revision_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Extension Registry Revision */
        get: operations["get_extension_registry_revision_config_extension_registry_revisions__extension_registry_revision_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/extension-registry-sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Extension Registry Sources */
        get: operations["list_extension_registry_sources_config_extension_registry_sources_get"];
        put?: never;
        /** Create Extension Registry Source */
        post: operations["create_extension_registry_source_config_extension_registry_sources_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/extension-registry-sources/{extension_registry_source_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Extension Registry Source */
        get: operations["get_extension_registry_source_config_extension_registry_sources__extension_registry_source_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Extension Registry Source */
        patch: operations["update_extension_registry_source_config_extension_registry_sources__extension_registry_source_id__patch"];
        trace?: never;
    };
    "/config/extension-registry-sources/{extension_registry_source_id}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Activate Extension Registry Source */
        post: operations["activate_extension_registry_source_config_extension_registry_sources__extension_registry_source_id__activate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/extension-registry-sources/{extension_registry_source_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Extension Registry Source Archived State */
        patch: operations["set_extension_registry_source_archived_state_config_extension_registry_sources__extension_registry_source_id__archive_patch"];
        trace?: never;
    };
    "/config/extension-registry-sources/{extension_registry_source_id}/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sync Extension Registry Source Route */
        post: operations["sync_extension_registry_source_route_config_extension_registry_sources__extension_registry_source_id__sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/ingestion-definitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Ingestion Definitions */
        get: operations["list_ingestion_definitions_config_ingestion_definitions_get"];
        put?: never;
        /** Create Ingestion Definition */
        post: operations["create_ingestion_definition_config_ingestion_definitions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/ingestion-definitions/{ingestion_definition_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Ingestion Definition */
        delete: operations["delete_ingestion_definition_config_ingestion_definitions__ingestion_definition_id__delete"];
        options?: never;
        head?: never;
        /** Update Ingestion Definition */
        patch: operations["update_ingestion_definition_config_ingestion_definitions__ingestion_definition_id__patch"];
        trace?: never;
    };
    "/config/ingestion-definitions/{ingestion_definition_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Ingestion Definition Archived State */
        patch: operations["set_ingestion_definition_archived_state_config_ingestion_definitions__ingestion_definition_id__archive_patch"];
        trace?: never;
    };
    "/config/publication-definitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Publication Definitions */
        get: operations["list_publication_definitions_config_publication_definitions_get"];
        put?: never;
        /** Create Publication Definition */
        post: operations["create_publication_definition_config_publication_definitions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/publication-definitions/{publication_definition_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Publication Definition */
        patch: operations["update_publication_definition_config_publication_definitions__publication_definition_id__patch"];
        trace?: never;
    };
    "/config/publication-definitions/{publication_definition_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Publication Definition Archived State */
        patch: operations["set_publication_definition_archived_state_config_publication_definitions__publication_definition_id__archive_patch"];
        trace?: never;
    };
    "/config/publication-keys": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Publication Keys */
        get: operations["list_publication_keys_config_publication_keys_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/source-assets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Source Assets */
        get: operations["list_source_assets_config_source_assets_get"];
        put?: never;
        /** Create Source Asset */
        post: operations["create_source_asset_config_source_assets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/source-assets/{source_asset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Source Asset */
        delete: operations["delete_source_asset_config_source_assets__source_asset_id__delete"];
        options?: never;
        head?: never;
        /** Update Source Asset */
        patch: operations["update_source_asset_config_source_assets__source_asset_id__patch"];
        trace?: never;
    };
    "/config/source-assets/{source_asset_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Source Asset Archived State */
        patch: operations["set_source_asset_archived_state_config_source_assets__source_asset_id__archive_patch"];
        trace?: never;
    };
    "/config/source-systems": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Source Systems */
        get: operations["list_source_systems_config_source_systems_get"];
        put?: never;
        /** Create Source System */
        post: operations["create_source_system_config_source_systems_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/source-systems/{source_system_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Source System */
        patch: operations["update_source_system_config_source_systems__source_system_id__patch"];
        trace?: never;
    };
    "/config/transformation-handlers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Transformation Handlers */
        get: operations["list_transformation_handlers_config_transformation_handlers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/transformation-packages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Transformation Packages */
        get: operations["list_transformation_packages_config_transformation_packages_get"];
        put?: never;
        /** Create Transformation Package */
        post: operations["create_transformation_package_config_transformation_packages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/config/transformation-packages/{transformation_package_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Transformation Package */
        patch: operations["update_transformation_package_config_transformation_packages__transformation_package_id__patch"];
        trace?: never;
    };
    "/config/transformation-packages/{transformation_package_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Set Transformation Package Archived State */
        patch: operations["set_transformation_package_archived_state_config_transformation_packages__transformation_package_id__archive_patch"];
        trace?: never;
    };
    "/contracts/publications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Publication Contracts */
        get: operations["list_publication_contracts_contracts_publications_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contracts/publications/{publication_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Publication Contract */
        get: operations["get_publication_contract_contracts_publications__publication_key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contracts/ui-descriptors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Ui Descriptors */
        get: operations["list_ui_descriptors_contracts_ui_descriptors_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/auth-audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Auth Audit */
        get: operations["list_auth_audit_control_auth_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/operational-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Operational Summary */
        get: operations["get_operational_summary_control_operational_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/publication-audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Publication Audit */
        get: operations["get_publication_audit_control_publication_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/schedule-dispatches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Schedule Dispatches */
        get: operations["list_schedule_dispatches_control_schedule_dispatches_get"];
        put?: never;
        /** Create Schedule Dispatch */
        post: operations["create_schedule_dispatch_control_schedule_dispatches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/schedule-dispatches/{dispatch_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Schedule Dispatch */
        get: operations["get_schedule_dispatch_control_schedule_dispatches__dispatch_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/schedule-dispatches/{dispatch_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry Schedule Dispatch */
        post: operations["retry_schedule_dispatch_control_schedule_dispatches__dispatch_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/source-freshness": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Freshness */
        get: operations["get_source_freshness_control_source_freshness_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/source-lineage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Lineage */
        get: operations["get_source_lineage_control_source_lineage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/terminal/commands": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Terminal Commands */
        get: operations["list_terminal_commands_control_terminal_commands_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/control/terminal/execute": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Execute Terminal Command Endpoint */
        post: operations["execute_terminal_command_endpoint_control_terminal_execute_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/extensions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Extensions */
        get: operations["list_extensions_extensions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/functions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Functions */
        get: operations["list_functions_functions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ingest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Account Transactions */
        post: operations["ingest_account_transactions_ingest_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ingest/account-transactions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Account Transactions Alias */
        post: operations["ingest_account_transactions_alias_ingest_account_transactions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ingest/configured-csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Configured Csv */
        post: operations["ingest_configured_csv_ingest_configured_csv_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ingest/contract-prices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Contract Prices */
        post: operations["ingest_contract_prices_ingest_contract_prices_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ingest/ingestion-definitions/{ingestion_definition_id}/process": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Process Ingestion Definition */
        post: operations["process_ingestion_definition_ingest_ingestion_definitions__ingestion_definition_id__process_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ingest/subscriptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Subscriptions */
        post: operations["ingest_subscriptions_ingest_subscriptions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/landing/{extension_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Run Landing Extension */
        post: operations["run_landing_extension_landing__extension_key__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Metrics */
        get: operations["metrics_metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/account-balance-trend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Account Balance Trend */
        get: operations["get_account_balance_trend_reports_account_balance_trend_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/affordability-ratios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Affordability Ratios */
        get: operations["get_affordability_ratios_reports_affordability_ratios_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/attention-items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Attention Items */
        get: operations["get_attention_items_reports_attention_items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/budget-progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Budget Progress */
        get: operations["get_budget_progress_reports_budget_progress_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/budget-variance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Budget Variance */
        get: operations["get_budget_variance_reports_budget_variance_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/contract-prices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Contract Price Current */
        get: operations["get_contract_price_current_reports_contract_prices_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/contract-renewal-watchlist": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Contract Renewal Watchlist */
        get: operations["get_contract_renewal_watchlist_reports_contract_renewal_watchlist_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/contract-review-candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Contract Review Candidates */
        get: operations["get_contract_review_candidates_reports_contract_review_candidates_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/cost-trend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Cost Trend */
        get: operations["get_cost_trend_reports_cost_trend_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/current-dimensions/{dimension_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Current Dimension Report */
        get: operations["get_current_dimension_report_reports_current_dimensions__dimension_name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/electricity-prices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Electricity Price Current */
        get: operations["get_electricity_price_current_reports_electricity_prices_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/household-cost-model": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Household Cost Model */
        get: operations["get_household_cost_model_reports_household_cost_model_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/household-overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Household Overview */
        get: operations["get_household_overview_reports_household_overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/loan-overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Loan Overview */
        get: operations["get_loan_overview_reports_loan_overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/loan-schedule/{loan_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Loan Schedule */
        get: operations["get_loan_schedule_reports_loan_schedule__loan_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/loan-variance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Loan Variance */
        get: operations["get_loan_variance_reports_loan_variance_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/monthly-cashflow": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Monthly Cashflow */
        get: operations["get_monthly_cashflow_reports_monthly_cashflow_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/monthly-cashflow-by-counterparty": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Monthly Cashflow By Counterparty */
        get: operations["get_monthly_cashflow_by_counterparty_reports_monthly_cashflow_by_counterparty_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/operating-baseline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Operating Baseline */
        get: operations["get_operating_baseline_reports_operating_baseline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/recent-changes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Recent Changes */
        get: operations["get_recent_changes_reports_recent_changes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/recent-large-transactions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Recent Large Transactions */
        get: operations["get_recent_large_transactions_reports_recent_large_transactions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/recurring-cost-baseline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Recurring Cost Baseline */
        get: operations["get_recurring_cost_baseline_reports_recurring_cost_baseline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/spend-by-category-monthly": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Spend By Category Monthly */
        get: operations["get_spend_by_category_monthly_reports_spend_by_category_monthly_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/subscription-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Subscription Summary */
        get: operations["get_subscription_summary_reports_subscription_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/transaction-anomalies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Transaction Anomalies */
        get: operations["get_transaction_anomalies_reports_transaction_anomalies_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/upcoming-fixed-costs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Upcoming Fixed Costs */
        get: operations["get_upcoming_fixed_costs_reports_upcoming_fixed_costs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/usage-vs-price": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Usage Vs Price */
        get: operations["get_usage_vs_price_reports_usage_vs_price_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/utility-cost-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Utility Cost Summary */
        get: operations["get_utility_cost_summary_reports_utility_cost_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/utility-cost-trend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Utility Cost Trend */
        get: operations["get_utility_cost_trend_reports_utility_cost_trend_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/reports/{extension_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Run Reporting Extension */
        get: operations["run_reporting_extension_reports__extension_key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry Run */
        post: operations["retry_run_runs__run_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sources */
        get: operations["list_sources_sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/transformation-audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Transformation Audit */
        get: operations["get_transformation_audit_transformation_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/transformations/{extension_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Run Transformation Extension */
        get: operations["run_transformation_extension_transformations__extension_key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AccountBalanceTrendResponse */
        AccountBalanceTrendResponse: {
            /** Rows */
            rows: components["schemas"]["AccountBalanceTrendRow"][];
        };
        /** AccountBalanceTrendRow */
        AccountBalanceTrendRow: {
            /** Account Id */
            account_id: string;
            /** Booking Month */
            booking_month: string;
            /** Cumulative Balance */
            cumulative_balance: string;
            /** Net Change */
            net_change: string;
            /** Transaction Count */
            transaction_count: number;
        };
        /** AffordabilityRatiosResponse */
        AffordabilityRatiosResponse: {
            /** Rows */
            rows: components["schemas"]["AffordabilityRatiosRow"][];
        };
        /** AffordabilityRatiosRow */
        AffordabilityRatiosRow: {
            /** Assessment */
            assessment: string;
            /** Currency */
            currency: string;
            /** Denominator */
            denominator: string;
            /** Numerator */
            numerator: string;
            /** Period Label */
            period_label: string;
            /** Ratio */
            ratio: string;
            /** Ratio Name */
            ratio_name: string;
        };
        /** ArchivedStateRequest */
        ArchivedStateRequest: {
            /** Archived */
            archived: boolean;
        };
        /** AttentionItemRow */
        AttentionItemRow: {
            /** Detail */
            detail: string;
            /** Item Id */
            item_id: string;
            /** Item Type */
            item_type: string;
            /** Severity */
            severity: number;
            /** Source Domain */
            source_domain: string;
            /** Title */
            title: string;
        };
        /** AttentionItemsResponse */
        AttentionItemsResponse: {
            /** Rows */
            rows: components["schemas"]["AttentionItemRow"][];
        };
        /** BudgetProgressCurrentRow */
        BudgetProgressCurrentRow: {
            /** Budget Name */
            budget_name: string;
            /** Category Id */
            category_id: string;
            /** Currency */
            currency: string;
            /** Remaining */
            remaining: string;
            /** Spent Amount */
            spent_amount: string;
            /** Target Amount */
            target_amount: string;
            /** Utilization Pct */
            utilization_pct: string;
        };
        /** BudgetProgressResponse */
        BudgetProgressResponse: {
            /** Rows */
            rows: components["schemas"]["BudgetProgressCurrentRow"][];
        };
        /** BudgetVarianceResponse */
        BudgetVarianceResponse: {
            /** Rows */
            rows: components["schemas"]["BudgetVarianceRow"][];
        };
        /** BudgetVarianceRow */
        BudgetVarianceRow: {
            /** Actual Amount */
            actual_amount: string;
            /** Budget Name */
            budget_name: string;
            /** Category Id */
            category_id: string;
            /** Currency */
            currency: string;
            /** Period Label */
            period_label: string;
            /** Status */
            status: string;
            /** Target Amount */
            target_amount: string;
            /** Variance */
            variance: string;
            /** Variance Pct */
            variance_pct?: string | null;
        };
        /** CategoryDeleteResponse */
        CategoryDeleteResponse: {
            /** Rule Id */
            rule_id: string;
            /** Status */
            status: string;
        };
        /** CategoryOverrideDeleteResponse */
        CategoryOverrideDeleteResponse: {
            /** Counterparty Name */
            counterparty_name: string;
            /** Status */
            status: string;
        };
        /** CategoryOverrideRow */
        CategoryOverrideRow: {
            /** Category */
            category: string;
            /** Counterparty Name */
            counterparty_name?: string | null;
        };
        /** CategoryOverridesResponse */
        CategoryOverridesResponse: {
            /** Rows */
            rows: components["schemas"]["CategoryOverrideRow"][];
        };
        /** CategoryRuleRow */
        CategoryRuleRow: {
            /** Category */
            category: string;
            /** Pattern */
            pattern: string;
            /** Priority */
            priority: number;
            /** Rule Id */
            rule_id?: string | null;
        };
        /** CategoryRulesResponse */
        CategoryRulesResponse: {
            /** Rows */
            rows: components["schemas"]["CategoryRuleRow"][];
        };
        /** ColumnMappingPreviewRequest */
        ColumnMappingPreviewRequest: {
            /** Column Mapping Id */
            column_mapping_id: string;
            /** Dataset Contract Id */
            dataset_contract_id: string;
            /**
             * Preview Limit
             * @default 5
             */
            preview_limit: number;
            /** Sample Csv */
            sample_csv: string;
        };
        /** ColumnMappingRequest */
        ColumnMappingRequest: {
            /** Column Mapping Id */
            column_mapping_id: string;
            /** Dataset Contract Id */
            dataset_contract_id: string;
            /** Rules */
            rules: components["schemas"]["ColumnMappingRuleRequest"][];
            /** Source System Id */
            source_system_id: string;
            /** Version */
            version: number;
        };
        /** ColumnMappingRuleRequest */
        ColumnMappingRuleRequest: {
            /** Default Value */
            default_value?: string | null;
            /** Function Key */
            function_key?: string | null;
            /** Source Column */
            source_column?: string | null;
            /** Target Column */
            target_column: string;
        };
        /**
         * ColumnType
         * @enum {string}
         */
        ColumnType: "string" | "integer" | "decimal" | "date" | "datetime" | "boolean";
        /** ConfiguredIngestionProcessResponseModel */
        ConfiguredIngestionProcessResponseModel: {
            /** Promotions */
            promotions?: components["schemas"]["PromotionResultModel"][] | null;
            result: components["schemas"]["ConfiguredIngestionProcessResultModel"];
        };
        /** ConfiguredIngestionProcessResultModel */
        ConfiguredIngestionProcessResultModel: {
            /** Discovered Files */
            discovered_files: number;
            /** Ingestion Definition Id */
            ingestion_definition_id: string;
            /** Processed Files */
            processed_files: number;
            /** Rejected Files */
            rejected_files: number;
            /** Run Ids */
            run_ids: string[];
        };
        /** ContractPriceCurrentResponse */
        ContractPriceCurrentResponse: {
            /** Contract Type */
            contract_type?: string | null;
            /** Rows */
            rows: components["schemas"]["ContractPriceCurrentRow"][];
            /** Status */
            status?: string | null;
        };
        /** ContractPriceCurrentRow */
        ContractPriceCurrentRow: {
            /** Billing Cycle */
            billing_cycle: string;
            /** Contract Id */
            contract_id: string;
            /** Contract Name */
            contract_name: string;
            /** Contract Type */
            contract_type: string;
            /** Currency */
            currency: string;
            /** Price Component */
            price_component: string;
            /** Provider */
            provider: string;
            /** Quantity Unit */
            quantity_unit?: string | null;
            /** Status */
            status: string;
            /** Unit Price */
            unit_price: string;
            /** Valid From */
            valid_from: string;
            /** Valid To */
            valid_to?: string | null;
        };
        /** ContractRenewalWatchlistResponse */
        ContractRenewalWatchlistResponse: {
            /** Rows */
            rows: components["schemas"]["ContractRenewalWatchlistRow"][];
        };
        /** ContractRenewalWatchlistRow */
        ContractRenewalWatchlistRow: {
            /** Contract Duration Days */
            contract_duration_days?: number | null;
            /** Contract Id */
            contract_id: string;
            /** Contract Name */
            contract_name: string;
            /** Currency */
            currency: string;
            /** Current Price */
            current_price: string;
            /** Days Until Renewal */
            days_until_renewal: number;
            /** Provider */
            provider: string;
            /** Renewal Date */
            renewal_date: string;
            /** Utility Type */
            utility_type: string;
        };
        /** ContractReviewCandidatesResponse */
        ContractReviewCandidatesResponse: {
            /** Rows */
            rows: components["schemas"]["ContractReviewCandidatesRow"][];
        };
        /** ContractReviewCandidatesRow */
        ContractReviewCandidatesRow: {
            /** Contract Id */
            contract_id: string;
            /** Currency */
            currency: string;
            /** Current Price */
            current_price: string;
            /** Market Reference */
            market_reference?: string | null;
            /** Provider */
            provider: string;
            /** Reason */
            reason: string;
            /** Score */
            score: number;
            /** Utility Type */
            utility_type: string;
        };
        /** CostTrend12MRow */
        CostTrend12MRow: {
            /** Amount */
            amount: string;
            /** Change Pct */
            change_pct?: string | null;
            /** Cost Type */
            cost_type: string;
            /** Currency */
            currency: string;
            /** Period Label */
            period_label: string;
            /** Prev Amount */
            prev_amount?: string | null;
        };
        /** CostTrendResponse */
        CostTrendResponse: {
            /** Rows */
            rows: components["schemas"]["CostTrend12MRow"][];
        };
        /** CreateCategoryRequest */
        CreateCategoryRequest: {
            /** Category Id */
            category_id: string;
            /** Display Name */
            display_name: string;
            /**
             * Domain
             * @default finance
             */
            domain: string;
            /**
             * Is Budget Eligible
             * @default true
             */
            is_budget_eligible: boolean;
            /** Parent Id */
            parent_id?: string | null;
        };
        /** CurrentDimensionResponse */
        CurrentDimensionResponse: {
            /** Dimension */
            dimension: string;
            /** Rows */
            rows: (components["schemas"]["DimAccountRow"] | components["schemas"]["DimCounterpartyRow"] | components["schemas"]["DimContractRow"] | components["schemas"]["DimCategoryRow"] | components["schemas"]["DimMeterRow"] | components["schemas"]["DimBudgetRow"] | components["schemas"]["DimLoanRow"] | components["schemas"]["DimEntityRow"])[];
        };
        /** CurrentOperatingBaselineRow */
        CurrentOperatingBaselineRow: {
            /** Baseline Type */
            baseline_type: string;
            /** Currency */
            currency: string;
            /** Description */
            description: string;
            /** Period Label */
            period_label: string;
            /** Value */
            value: string;
        };
        /** DatasetColumnRequest */
        DatasetColumnRequest: {
            /** Name */
            name: string;
            /**
             * Required
             * @default true
             */
            required: boolean;
            type: components["schemas"]["ColumnType"];
        };
        /** DatasetContractRequest */
        DatasetContractRequest: {
            /** Allow Extra Columns */
            allow_extra_columns: boolean;
            /** Columns */
            columns: components["schemas"]["DatasetColumnRequest"][];
            /** Dataset Contract Id */
            dataset_contract_id: string;
            /** Dataset Name */
            dataset_name: string;
            /** Version */
            version: number;
        };
        /** DimAccountRow */
        DimAccountRow: {
            /** Account Id */
            account_id: string;
            /** Currency */
            currency?: string | null;
            /** Sk */
            sk: string;
        };
        /** DimBudgetRow */
        DimBudgetRow: {
            /** Budget Id */
            budget_id: string;
            /** Budget Name */
            budget_name?: string | null;
            /** Category Id */
            category_id?: string | null;
            /** Currency */
            currency?: string | null;
            /** Period Type */
            period_type?: string | null;
            /** Sk */
            sk: string;
        };
        /** DimCategoryRow */
        DimCategoryRow: {
            /** Category Id */
            category_id: string;
            /** Display Name */
            display_name?: string | null;
            /** Domain */
            domain?: string | null;
            /** Is Budget Eligible */
            is_budget_eligible?: boolean | null;
            /** Is System */
            is_system?: boolean | null;
            /** Parent Id */
            parent_id?: string | null;
            /** Sk */
            sk: string;
        };
        /** DimContractRow */
        DimContractRow: {
            /** Contract Id */
            contract_id: string;
            /** Contract Name */
            contract_name?: string | null;
            /** Contract Type */
            contract_type?: string | null;
            /** Currency */
            currency?: string | null;
            /** End Date */
            end_date?: string | null;
            /** Provider */
            provider?: string | null;
            /** Sk */
            sk: string;
            /** Start Date */
            start_date?: string | null;
        };
        /** DimCounterpartyRow */
        DimCounterpartyRow: {
            /** Category */
            category?: string | null;
            /** Counterparty Name */
            counterparty_name: string;
            /** Sk */
            sk: string;
        };
        /** DimEntityRow */
        DimEntityRow: {
            /** Area */
            area?: string | null;
            /** Device Name */
            device_name?: string | null;
            /** Entity Class */
            entity_class?: string | null;
            /** Entity Domain */
            entity_domain?: string | null;
            /** Entity Id */
            entity_id: string;
            /** Entity Name */
            entity_name?: string | null;
            /** Integration */
            integration?: string | null;
            /** Sk */
            sk: string;
            /** Unit */
            unit?: string | null;
        };
        /** DimLoanRow */
        DimLoanRow: {
            /** Annual Rate */
            annual_rate?: string | null;
            /** Currency */
            currency?: string | null;
            /** Lender */
            lender?: string | null;
            /** Loan Id */
            loan_id: string;
            /** Loan Name */
            loan_name?: string | null;
            /** Loan Type */
            loan_type?: string | null;
            /** Payment Frequency */
            payment_frequency?: string | null;
            /** Principal */
            principal?: string | null;
            /** Sk */
            sk: string;
            /** Start Date */
            start_date?: string | null;
            /** Term Months */
            term_months?: number | null;
        };
        /** DimMeterRow */
        DimMeterRow: {
            /** Default Unit */
            default_unit?: string | null;
            /** Location */
            location?: string | null;
            /** Meter Id */
            meter_id: string;
            /** Meter Name */
            meter_name?: string | null;
            /** Sk */
            sk: string;
            /** Utility Type */
            utility_type?: string | null;
        };
        /** ElectricityPriceCurrentResponse */
        ElectricityPriceCurrentResponse: {
            /** Rows */
            rows: components["schemas"]["ElectricityPriceCurrentRow"][];
        };
        /** ElectricityPriceCurrentRow */
        ElectricityPriceCurrentRow: {
            /** Billing Cycle */
            billing_cycle: string;
            /** Contract Id */
            contract_id: string;
            /** Contract Name */
            contract_name: string;
            /** Contract Type */
            contract_type: string;
            /** Currency */
            currency: string;
            /** Price Component */
            price_component: string;
            /** Provider */
            provider: string;
            /** Quantity Unit */
            quantity_unit?: string | null;
            /** Status */
            status: string;
            /** Unit Price */
            unit_price: string;
            /** Valid From */
            valid_from: string;
            /** Valid To */
            valid_to?: string | null;
        };
        /** ExecutionScheduleRequest */
        ExecutionScheduleRequest: {
            /** Cron Expression */
            cron_expression: string;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /**
             * Max Concurrency
             * @default 1
             */
            max_concurrency: number;
            /** Schedule Id */
            schedule_id: string;
            /** Target Kind */
            target_kind: string;
            /** Target Ref */
            target_ref: string;
            /**
             * Timezone
             * @default UTC
             */
            timezone: string;
        };
        /** ExpenseShockRequest */
        ExpenseShockRequest: {
            /** Expense Pct Delta */
            expense_pct_delta: string;
            /** Label */
            label?: string | null;
            /** Projection Months */
            projection_months?: number | null;
        };
        /** ExtensionRegistryActivationRequest */
        ExtensionRegistryActivationRequest: {
            /** Extension Registry Revision Id */
            extension_registry_revision_id: string;
        };
        /** ExtensionRegistrySourceRequest */
        ExtensionRegistrySourceRequest: {
            /** Auth Secret Key */
            auth_secret_key?: string | null;
            /** Auth Secret Name */
            auth_secret_name?: string | null;
            /** Desired Ref */
            desired_ref?: string | null;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /** Extension Registry Source Id */
            extension_registry_source_id: string;
            /** Location */
            location: string;
            /** Name */
            name: string;
            /** Source Kind */
            source_kind: string;
            /** Subdirectory */
            subdirectory?: string | null;
        };
        /** ExtensionRegistrySyncRequest */
        ExtensionRegistrySyncRequest: {
            /**
             * Activate
             * @default false
             */
            activate: boolean;
        };
        /** ExtensionReportResponse */
        ExtensionReportResponse: {
            /** Result */
            result: unknown;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HaApprovalProposalListModel */
        HaApprovalProposalListModel: {
            /** Proposals */
            proposals: components["schemas"]["HaApprovalProposalModel"][];
        };
        /** HaApprovalProposalModel */
        HaApprovalProposalModel: {
            /** Action Id */
            action_id: string;
            /** Approved At */
            approved_at?: string | null;
            /** Created At */
            created_at: string;
            /** Dismissed At */
            dismissed_at?: string | null;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Notification Id */
            notification_id: string;
            /** Policy Id */
            policy_id: string;
            /** Policy Name */
            policy_name: string;
            /** Status */
            status: string;
            /** Value */
            value?: string | null;
            /** Verdict */
            verdict: string;
        };
        /** HaIngestRequest */
        HaIngestRequest: {
            /** Run Id */
            run_id?: string | null;
            /** Source System */
            source_system?: string | null;
            /** States */
            states: components["schemas"]["HaStateObject"][];
        };
        /** HaMqttStatusModel */
        HaMqttStatusModel: {
            /** Connected */
            connected: boolean;
            /** Contract Entity Count */
            contract_entity_count: number;
            /** Enabled */
            enabled: boolean;
            /** Entity Count */
            entity_count: number;
            /** Last Publish At */
            last_publish_at?: string | null;
            /** Publication Keys */
            publication_keys: string[];
            /** Publish Count */
            publish_count: number;
            /** Static Entity Count */
            static_entity_count: number;
        };
        /** HaStateObject */
        HaStateObject: {
            /** Attributes */
            attributes?: {
                [key: string]: unknown;
            } | null;
            /** Entity Id */
            entity_id: string;
            /** Last Changed */
            last_changed?: string | null;
            /** Last Updated */
            last_updated?: string | null;
            /** State */
            state: string;
        };
        /** HouseholdCostModelResponse */
        HouseholdCostModelResponse: {
            /** Cost Type */
            cost_type?: string | null;
            /** Period Label */
            period_label?: string | null;
            /** Rows */
            rows: components["schemas"]["HouseholdCostModelRow"][];
        };
        /** HouseholdCostModelRow */
        HouseholdCostModelRow: {
            /** Amount */
            amount: string;
            /** Cost Type */
            cost_type: string;
            /** Currency */
            currency: string;
            /** Period Label */
            period_label: string;
            /** Source Domain */
            source_domain: string;
        };
        /** HouseholdOverviewResponse */
        HouseholdOverviewResponse: {
            /** Rows */
            rows: components["schemas"]["HouseholdOverviewRow"][];
        };
        /** HouseholdOverviewRow */
        HouseholdOverviewRow: {
            /** Account Balance Direction */
            account_balance_direction: string;
            /** Balance Net Change */
            balance_net_change: string;
            /** Cashflow Expense */
            cashflow_expense: string;
            /** Cashflow Income */
            cashflow_income: string;
            /** Cashflow Net */
            cashflow_net: string;
            /** Currency */
            currency: string;
            /** Current Month */
            current_month: string;
            /** Subscription Total Monthly */
            subscription_total_monthly: string;
            /** Utility Cost Total */
            utility_cost_total: string;
        };
        /** IncomeChangeRequest */
        IncomeChangeRequest: {
            /** Label */
            label?: string | null;
            /** Monthly Income Delta */
            monthly_income_delta: string;
            /** Projection Months */
            projection_months?: number | null;
        };
        /** IngestionDefinitionRequest */
        IngestionDefinitionRequest: {
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /** Failed Path */
            failed_path?: string | null;
            /**
             * File Pattern
             * @default *.csv
             */
            file_pattern: string;
            /** Ingestion Definition Id */
            ingestion_definition_id: string;
            /** Output File Name */
            output_file_name?: string | null;
            /** Poll Interval Seconds */
            poll_interval_seconds?: number | null;
            /** Processed Path */
            processed_path?: string | null;
            /** Request Headers */
            request_headers?: components["schemas"]["RequestHeaderRequest"][];
            /** Request Method */
            request_method?: string | null;
            /** Request Timeout Seconds */
            request_timeout_seconds?: number | null;
            /** Request Url */
            request_url?: string | null;
            /** Response Format */
            response_format?: string | null;
            /** Schedule Mode */
            schedule_mode: string;
            /** Source Asset Id */
            source_asset_id: string;
            /** Source Name */
            source_name?: string | null;
            /**
             * Source Path
             * @default
             */
            source_path: string;
            /** Transport */
            transport: string;
        };
        /** LoanOverviewResponse */
        LoanOverviewResponse: {
            /** Rows */
            rows: components["schemas"]["LoanOverviewRow"][];
        };
        /** LoanOverviewRow */
        LoanOverviewRow: {
            /** Currency */
            currency: string;
            /** Current Balance Estimate */
            current_balance_estimate: string;
            /** Lender */
            lender: string;
            /** Loan Id */
            loan_id: string;
            /** Loan Name */
            loan_name: string;
            /** Monthly Payment */
            monthly_payment: string;
            /** Original Principal */
            original_principal: string;
            /** Remaining Months */
            remaining_months: number;
            /** Total Interest Paid */
            total_interest_paid: string;
            /** Total Interest Projected */
            total_interest_projected: string;
        };
        /** LoanRepaymentVarianceRow */
        LoanRepaymentVarianceRow: {
            /** Actual Balance Estimate */
            actual_balance_estimate: string;
            /** Actual Payment */
            actual_payment: string;
            /** Currency */
            currency: string;
            /** Loan Id */
            loan_id: string;
            /** Loan Name */
            loan_name: string;
            /** Projected Balance */
            projected_balance: string;
            /** Projected Payment */
            projected_payment: string;
            /** Repayment Month */
            repayment_month: string;
            /** Variance */
            variance: string;
        };
        /** LoanScheduleProjectedRow */
        LoanScheduleProjectedRow: {
            /** Currency */
            currency: string;
            /** Interest Portion */
            interest_portion: string;
            /** Loan Id */
            loan_id: string;
            /** Loan Name */
            loan_name: string;
            /** Payment */
            payment: string;
            /** Payment Date */
            payment_date: string;
            /** Period */
            period: number;
            /** Principal Portion */
            principal_portion: string;
            /** Remaining Balance */
            remaining_balance: string;
        };
        /** LoanScheduleResponse */
        LoanScheduleResponse: {
            /** Loan Id */
            loan_id: string;
            /** Rows */
            rows: components["schemas"]["LoanScheduleProjectedRow"][];
        };
        /** LoanVarianceResponse */
        LoanVarianceResponse: {
            /** Loan Id */
            loan_id?: string | null;
            /** Rows */
            rows: components["schemas"]["LoanRepaymentVarianceRow"][];
        };
        /** LoanWhatIfRequest */
        LoanWhatIfRequest: {
            /** Annual Rate */
            annual_rate?: string | null;
            /** Extra Repayment */
            extra_repayment?: string | null;
            /** Label */
            label?: string | null;
            /** Loan Id */
            loan_id: string;
            /** Term Months */
            term_months?: number | null;
        };
        /** LocalUserCreateRequest */
        LocalUserCreateRequest: {
            /** Password */
            password: string;
            role: components["schemas"]["UserRole"];
            /** Username */
            username: string;
        };
        /** LocalUserModel */
        LocalUserModel: {
            /** Auth Provider */
            auth_provider: string;
            /** Created At */
            created_at: string;
            /** Enabled */
            enabled: boolean;
            /** Last Login At */
            last_login_at?: string | null;
            /** Role */
            role: string;
            /** User Id */
            user_id: string;
            /** Username */
            username: string;
        };
        /** LocalUserPasswordResetRequest */
        LocalUserPasswordResetRequest: {
            /** Password */
            password: string;
        };
        /** LocalUserResponseModel */
        LocalUserResponseModel: {
            user: components["schemas"]["LocalUserModel"];
        };
        /** LocalUserUpdateRequest */
        LocalUserUpdateRequest: {
            /** Enabled */
            enabled?: boolean | null;
            role?: components["schemas"]["UserRole"] | null;
        };
        /** LoginRequest */
        LoginRequest: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** MonthlyCashflowByCounterpartyResponse */
        MonthlyCashflowByCounterpartyResponse: {
            /** Counterparty */
            counterparty?: string | null;
            /** From Month */
            from_month?: string | null;
            /** Rows */
            rows: components["schemas"]["MonthlyCashflowByCounterpartyRow"][];
            /** To Month */
            to_month?: string | null;
        };
        /** MonthlyCashflowByCounterpartyRow */
        MonthlyCashflowByCounterpartyRow: {
            /** Booking Month */
            booking_month: string;
            /** Counterparty Name */
            counterparty_name: string;
            /** Expense */
            expense: string;
            /** Income */
            income: string;
            /** Net */
            net: string;
            /** Transaction Count */
            transaction_count: number;
        };
        /** MonthlyCashflowResponse */
        MonthlyCashflowResponse: {
            /** From Month */
            from_month?: string | null;
            /** Rows */
            rows: components["schemas"]["MonthlyCashflowRow"][];
            /** To Month */
            to_month?: string | null;
        };
        /** MonthlyCashflowRow */
        MonthlyCashflowRow: {
            /** Booking Month */
            booking_month: string;
            /** Expense */
            expense: string;
            /** Income */
            income: string;
            /** Net */
            net: string;
            /** Transaction Count */
            transaction_count: number;
        };
        /** OperatingBaselineResponse */
        OperatingBaselineResponse: {
            /** Rows */
            rows: components["schemas"]["CurrentOperatingBaselineRow"][];
        };
        /** PromotionResultModel */
        PromotionResultModel: {
            /** Facts Loaded */
            facts_loaded: number;
            /** Marts Refreshed */
            marts_refreshed: string[];
            /** Publication Keys */
            publication_keys: string[];
            /** Run Id */
            run_id?: string | null;
            /** Skip Reason */
            skip_reason?: string | null;
            /** Skipped */
            skipped: boolean;
        };
        /** PublicationColumnContractModel */
        PublicationColumnContractModel: {
            /** Aggregation */
            aggregation?: string | null;
            /** Description */
            description: string;
            /** Filterable */
            filterable: boolean;
            /** Grain */
            grain?: string | null;
            /** Json Type */
            json_type: string;
            /** Name */
            name: string;
            /** Nullable */
            nullable: boolean;
            /** Semantic Role */
            semantic_role: string;
            /** Sortable */
            sortable: boolean;
            /** Storage Type */
            storage_type: string;
            /** Unit */
            unit?: string | null;
        };
        /** PublicationContractModel */
        PublicationContractModel: {
            /** Columns */
            columns: components["schemas"]["PublicationColumnContractModel"][];
            /** Description */
            description?: string | null;
            /** Display Name */
            display_name: string;
            /** Lineage Required */
            lineage_required: boolean;
            /** Pack Name */
            pack_name?: string | null;
            /** Pack Version */
            pack_version?: string | null;
            /** Publication Key */
            publication_key: string;
            /** Relation Name */
            relation_name: string;
            /** Renderer Hints */
            renderer_hints: {
                [key: string]: string;
            };
            /** Retention Policy */
            retention_policy: string;
            /** Schema Name */
            schema_name: string;
            /** Schema Version */
            schema_version: string;
            /** Supported Renderers */
            supported_renderers: string[];
            /** Ui Descriptor Keys */
            ui_descriptor_keys: string[];
            /** Visibility */
            visibility: string;
        };
        /** PublicationContractsResponse */
        PublicationContractsResponse: {
            /** Publication Contracts */
            publication_contracts: components["schemas"]["PublicationContractModel"][];
        };
        /** PublicationDefinitionRequest */
        PublicationDefinitionRequest: {
            /** Description */
            description?: string | null;
            /** Name */
            name: string;
            /** Publication Definition Id */
            publication_definition_id: string;
            /** Publication Key */
            publication_key: string;
            /** Transformation Package Id */
            transformation_package_id: string;
        };
        /** RecentChangesResponse */
        RecentChangesResponse: {
            /** Rows */
            rows: components["schemas"]["RecentSignificantChangeRow"][];
        };
        /** RecentLargeTransactionsResponse */
        RecentLargeTransactionsResponse: {
            /** Rows */
            rows: components["schemas"]["RecentLargeTransactionsRow"][];
        };
        /** RecentLargeTransactionsRow */
        RecentLargeTransactionsRow: {
            /** Account Id */
            account_id: string;
            /** Amount */
            amount: string;
            /** Booked At */
            booked_at: string;
            /** Booking Month */
            booking_month: string;
            /** Counterparty Name */
            counterparty_name: string;
            /** Currency */
            currency: string;
            /** Description */
            description?: string | null;
            /** Direction */
            direction: string;
            /** Transaction Id */
            transaction_id: string;
        };
        /** RecentSignificantChangeRow */
        RecentSignificantChangeRow: {
            /** Change Pct */
            change_pct?: string | null;
            /** Change Type */
            change_type: string;
            /** Current Value */
            current_value: string;
            /** Description */
            description: string;
            /** Direction */
            direction: string;
            /** Period */
            period: string;
            /** Previous Value */
            previous_value: string;
        };
        /** RecurringCostBaselineResponse */
        RecurringCostBaselineResponse: {
            /** Rows */
            rows: components["schemas"]["RecurringCostBaselineRow"][];
        };
        /** RecurringCostBaselineRow */
        RecurringCostBaselineRow: {
            /** Confidence */
            confidence: string;
            /** Cost Source */
            cost_source: string;
            /** Counterparty Or Contract */
            counterparty_or_contract: string;
            /** Currency */
            currency: string;
            /** Last Occurrence */
            last_occurrence?: string | null;
            /** Monthly Amount */
            monthly_amount: string;
        };
        /** RequestHeaderRequest */
        RequestHeaderRequest: {
            /** Name */
            name: string;
            /** Secret Key */
            secret_key: string;
            /** Secret Name */
            secret_name: string;
        };
        /** RunIssueModel */
        RunIssueModel: {
            /** Code */
            code: string;
            /** Column */
            column?: string | null;
            /** Message */
            message: string;
            /** Row Number */
            row_number?: number | null;
        };
        /** RunModel */
        RunModel: {
            /** Context */
            context?: {
                [key: string]: unknown;
            } | null;
            /** Created At */
            created_at: string;
            /** Dataset Name */
            dataset_name: string;
            /** File Name */
            file_name: string;
            /** Header */
            header: string[];
            /** Issues */
            issues: components["schemas"]["RunIssueModel"][];
            /** Manifest Path */
            manifest_path: string;
            /** Passed */
            passed: boolean;
            /** Raw Path */
            raw_path: string;
            /** Recovery */
            recovery?: {
                [key: string]: unknown;
            } | null;
            /** Row Count */
            row_count: number;
            /** Run Id */
            run_id: string;
            /** Sha256 */
            sha256: string;
            /** Source Name */
            source_name: string;
            /** Status */
            status: string;
        };
        /** RunMutationResponseModel */
        RunMutationResponseModel: {
            promotion?: components["schemas"]["PromotionResultModel"] | null;
            run: components["schemas"]["RunModel"];
        };
        /** ScheduleDispatchModel */
        ScheduleDispatchModel: {
            /** Claim Expires At */
            claim_expires_at?: string | null;
            /** Claimed At */
            claimed_at?: string | null;
            /** Claimed By Worker Id */
            claimed_by_worker_id?: string | null;
            /** Completed At */
            completed_at?: string | null;
            /** Dispatch Id */
            dispatch_id: string;
            /** Enqueued At */
            enqueued_at: string;
            /** Failure Reason */
            failure_reason?: string | null;
            /** Run Ids */
            run_ids: string[];
            /** Schedule Id */
            schedule_id: string;
            /** Started At */
            started_at?: string | null;
            /** Status */
            status: string;
            /** Target Kind */
            target_kind: string;
            /** Target Ref */
            target_ref: string;
            /** Worker Detail */
            worker_detail?: string | null;
        };
        /** ScheduleDispatchRequest */
        ScheduleDispatchRequest: {
            /** Limit */
            limit?: number | null;
            /** Schedule Id */
            schedule_id?: string | null;
        };
        /** ScheduleDispatchResponseModel */
        ScheduleDispatchResponseModel: {
            dispatch: components["schemas"]["ScheduleDispatchModel"];
        };
        /** ServiceTokenCreateRequest */
        ServiceTokenCreateRequest: {
            /** Expires At */
            expires_at?: string | null;
            role: components["schemas"]["UserRole"];
            /** Scopes */
            scopes: string[];
            /** Token Name */
            token_name: string;
        };
        /** ServiceTokenCreateResponseModel */
        ServiceTokenCreateResponseModel: {
            service_token: components["schemas"]["ServiceTokenModel"];
            /** Token Value */
            token_value: string;
        };
        /** ServiceTokenModel */
        ServiceTokenModel: {
            /** Created At */
            created_at: string;
            /** Expired */
            expired: boolean;
            /** Expires At */
            expires_at?: string | null;
            /** Last Used At */
            last_used_at?: string | null;
            /** Revoked */
            revoked: boolean;
            /** Revoked At */
            revoked_at?: string | null;
            /** Role */
            role: string;
            /** Scopes */
            scopes: string[];
            /** Token Id */
            token_id: string;
            /** Token Name */
            token_name: string;
        };
        /** ServiceTokenResponseModel */
        ServiceTokenResponseModel: {
            service_token: components["schemas"]["ServiceTokenModel"];
        };
        /** SourceAssetRequest */
        SourceAssetRequest: {
            /** Asset Type */
            asset_type: string;
            /** Column Mapping Id */
            column_mapping_id: string;
            /** Dataset Contract Id */
            dataset_contract_id: string;
            /** Description */
            description?: string | null;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /** Name */
            name: string;
            /** Source Asset Id */
            source_asset_id: string;
            /** Source System Id */
            source_system_id: string;
            /** Transformation Package Id */
            transformation_package_id?: string | null;
        };
        /** SourceSystemRequest */
        SourceSystemRequest: {
            /** Description */
            description?: string | null;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /** Name */
            name: string;
            /** Schedule Mode */
            schedule_mode: string;
            /** Source System Id */
            source_system_id: string;
            /** Source Type */
            source_type: string;
            /** Transport */
            transport: string;
        };
        /** SpendByCategoryMonthlyResponse */
        SpendByCategoryMonthlyResponse: {
            /** Rows */
            rows: components["schemas"]["SpendByCategoryMonthlyRow"][];
        };
        /** SpendByCategoryMonthlyRow */
        SpendByCategoryMonthlyRow: {
            /** Booking Month */
            booking_month: string;
            /** Category */
            category?: string | null;
            /** Counterparty Name */
            counterparty_name: string;
            /** Total Expense */
            total_expense: string;
            /** Transaction Count */
            transaction_count: number;
        };
        /** SubscriptionSummaryResponse */
        SubscriptionSummaryResponse: {
            /** Currency */
            currency?: string | null;
            /** Rows */
            rows: components["schemas"]["SubscriptionSummaryRow"][];
            /** Status */
            status?: string | null;
        };
        /** SubscriptionSummaryRow */
        SubscriptionSummaryRow: {
            /** Amount */
            amount: string;
            /** Billing Cycle */
            billing_cycle: string;
            /** Contract Id */
            contract_id: string;
            /** Contract Name */
            contract_name: string;
            /** Currency */
            currency: string;
            /** End Date */
            end_date?: string | null;
            /** Monthly Equivalent */
            monthly_equivalent: string;
            /** Provider */
            provider: string;
            /** Start Date */
            start_date: string;
            /** Status */
            status: string;
        };
        /** TariffShockRequest */
        TariffShockRequest: {
            /** Label */
            label?: string | null;
            /** Projection Months */
            projection_months?: number | null;
            /** Tariff Pct Delta */
            tariff_pct_delta: string;
            /** Utility Type */
            utility_type?: string | null;
        };
        /** TerminalCommandModel */
        TerminalCommandModel: {
            /** Description */
            description: string;
            /** Mutating */
            mutating: boolean;
            /** Name */
            name: string;
            /** Usage */
            usage: string;
        };
        /** TerminalCommandsResponseModel */
        TerminalCommandsResponseModel: {
            /** Commands */
            commands: components["schemas"]["TerminalCommandModel"][];
        };
        /** TerminalExecutionModel */
        TerminalExecutionModel: {
            /** Command Name */
            command_name: string;
            /** Exit Code */
            exit_code: number;
            /** Mutating */
            mutating: boolean;
            /** Normalized Command */
            normalized_command: string;
            /** Result */
            result: {
                [key: string]: unknown;
            };
            /** Status */
            status: string;
            /** Stderr Lines */
            stderr_lines: string[];
            /** Stdout Lines */
            stdout_lines: string[];
        };
        /** TerminalExecutionRequest */
        TerminalExecutionRequest: {
            /** Command Line */
            command_line: string;
        };
        /** TerminalExecutionResponseModel */
        TerminalExecutionResponseModel: {
            execution: components["schemas"]["TerminalExecutionModel"];
        };
        /** TransactionAnomaliesResponse */
        TransactionAnomaliesResponse: {
            /** Rows */
            rows: components["schemas"]["TransactionAnomaliesRow"][];
        };
        /** TransactionAnomaliesRow */
        TransactionAnomaliesRow: {
            /** Amount */
            amount: string;
            /** Anomaly Reason */
            anomaly_reason: string;
            /** Anomaly Type */
            anomaly_type: string;
            /** Booking Date */
            booking_date: string;
            /** Counterparty Name */
            counterparty_name: string;
            /** Direction */
            direction: string;
            /** Transaction Id */
            transaction_id: string;
        };
        /** TransformationAuditResponse */
        TransformationAuditResponse: {
            /** Rows */
            rows: components["schemas"]["TransformationAuditRow"][];
        };
        /** TransformationAuditRow */
        TransformationAuditRow: {
            /** Accounts Upserted */
            accounts_upserted: number;
            /** Audit Id */
            audit_id?: string | null;
            /** Completed At */
            completed_at: string;
            /** Counterparties Upserted */
            counterparties_upserted: number;
            /** Duration Ms */
            duration_ms: number;
            /** Fact Rows */
            fact_rows: number;
            /** Input Run Id */
            input_run_id?: string | null;
            /** Started At */
            started_at: string;
        };
        /** TransformationPackageRequest */
        TransformationPackageRequest: {
            /** Description */
            description?: string | null;
            /** Handler Key */
            handler_key: string;
            /** Name */
            name: string;
            /** Transformation Package Id */
            transformation_package_id: string;
            /** Version */
            version: number;
        };
        /** UiDescriptorContractModel */
        UiDescriptorContractModel: {
            /** Default Filters */
            default_filters: {
                [key: string]: string;
            };
            /** Icon */
            icon?: string | null;
            /** Key */
            key: string;
            /** Kind */
            kind: string;
            /** Nav Label */
            nav_label: string;
            /** Nav Path */
            nav_path: string;
            /** Publication Keys */
            publication_keys: string[];
            /** Renderer Hints */
            renderer_hints: {
                [key: string]: string;
            };
            /** Required Permissions */
            required_permissions: string[];
            /** Supported Renderers */
            supported_renderers: string[];
        };
        /** UiDescriptorsResponse */
        UiDescriptorsResponse: {
            /** Ui Descriptors */
            ui_descriptors: components["schemas"]["UiDescriptorContractModel"][];
        };
        /** UpcomingFixedCostsResponse */
        UpcomingFixedCostsResponse: {
            /** Rows */
            rows: components["schemas"]["UpcomingFixedCostsRow"][];
        };
        /** UpcomingFixedCostsRow */
        UpcomingFixedCostsRow: {
            /** Confidence */
            confidence: string;
            /** Contract Name */
            contract_name: string;
            /** Currency */
            currency: string;
            /** Expected Amount */
            expected_amount: string;
            /** Expected Date */
            expected_date: string;
            /** Frequency */
            frequency: string;
            /** Provider */
            provider: string;
        };
        /** UsageVsPriceResponse */
        UsageVsPriceResponse: {
            /** Rows */
            rows: components["schemas"]["UsageVsPriceRow"][];
            /** Utility Type */
            utility_type?: string | null;
        };
        /** UsageVsPriceRow */
        UsageVsPriceRow: {
            /** Cost Change Pct */
            cost_change_pct?: string | null;
            /** Dominant Driver */
            dominant_driver?: string | null;
            /** Period */
            period: string;
            /** Price Change Pct */
            price_change_pct?: string | null;
            /** Usage Change Pct */
            usage_change_pct?: string | null;
            /** Utility Type */
            utility_type: string;
        };
        /**
         * UserRole
         * @enum {string}
         */
        UserRole: "reader" | "operator" | "admin";
        /** UtilityCostSummaryResponse */
        UtilityCostSummaryResponse: {
            /** From Period */
            from_period?: string | null;
            /**
             * Granularity
             * @default month
             */
            granularity: string;
            /** Meter Id */
            meter_id?: string | null;
            /** Rows */
            rows: components["schemas"]["UtilityCostSummaryRow"][];
            /** To Period */
            to_period?: string | null;
            /** Utility Type */
            utility_type?: string | null;
        };
        /** UtilityCostSummaryRow */
        UtilityCostSummaryRow: {
            /** Bill Count */
            bill_count: number;
            /** Billed Amount */
            billed_amount: string;
            /** Coverage Status */
            coverage_status: string;
            /** Currency */
            currency?: string | null;
            /** Meter Id */
            meter_id: string;
            /** Meter Name */
            meter_name: string;
            /** Period */
            period: string;
            /** Period End */
            period_end: string;
            /** Period Start */
            period_start: string;
            /** Unit Cost */
            unit_cost?: string | null;
            /** Usage Quantity */
            usage_quantity: string;
            /** Usage Record Count */
            usage_record_count: number;
            /** Usage Unit */
            usage_unit?: string | null;
            /** Utility Type */
            utility_type: string;
        };
        /** UtilityCostTrendResponse */
        UtilityCostTrendResponse: {
            /** Rows */
            rows: components["schemas"]["UtilityCostTrendRow"][];
            /** Utility Type */
            utility_type?: string | null;
        };
        /** UtilityCostTrendRow */
        UtilityCostTrendRow: {
            /** Billing Month */
            billing_month: string;
            /** Currency */
            currency?: string | null;
            /** Meter Count */
            meter_count: number;
            /** Total Cost */
            total_cost: string;
            /** Unit Price Effective */
            unit_price_effective?: string | null;
            /** Usage Amount */
            usage_amount: string;
            /** Utility Type */
            utility_type: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_categories_api_categories_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    create_category_api_categories_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateCategoryRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_actions_api_ha_actions_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_action_proposals_api_ha_actions_proposals_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HaApprovalProposalListModel"];
                };
            };
        };
    };
    get_action_proposal_api_ha_actions_proposals__action_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                action_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HaApprovalProposalModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approve_action_proposal_api_ha_actions_proposals__action_id__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                action_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HaApprovalProposalModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dismiss_action_proposal_api_ha_actions_proposals__action_id__dismiss_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                action_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HaApprovalProposalModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_actions_status_api_ha_actions_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_bridge_status_api_ha_bridge_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_ha_entities_api_ha_entities_get: {
        parameters: {
            query?: {
                entity_class?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ha_entity_history_api_ha_entities__entity_id__history_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                entity_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_ha_states_api_ha_ingest_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HaIngestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_mqtt_status_api_ha_mqtt_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HaMqttStatusModel"];
                };
            };
        };
    };
    get_policies_api_ha_policies_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    evaluate_policies_api_ha_policies_evaluate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_backup_freshness_api_homelab_backups_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_service_health_api_homelab_services_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_storage_risk_api_homelab_storage_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_workload_cost_7d_api_homelab_workloads_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_scenarios_route_api_scenarios_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_expense_shock_api_scenarios_expense_shock_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExpenseShockRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_income_change_api_scenarios_income_change_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncomeChangeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_loan_what_if_api_scenarios_loan_what_if_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoanWhatIfRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_tariff_shock_api_scenarios_tariff_shock_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TariffShockRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scenario_metadata_api_scenarios__scenario_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_scenario_api_scenarios__scenario_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scenario_assumptions_api_scenarios__scenario_id__assumptions_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_income_scenario_cashflow_api_scenarios__scenario_id__cashflow_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scenario_comparison_api_scenarios__scenario_id__comparison_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    oidc_callback_auth_callback_get: {
        parameters: {
            query?: {
                code?: string | null;
                state?: string | null;
                error?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_oidc_login_auth_login_get: {
        parameters: {
            query?: {
                return_to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    auth_me_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_service_tokens_auth_service_tokens_get: {
        parameters: {
            query?: {
                include_revoked?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_service_token_endpoint_auth_service_tokens_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServiceTokenCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServiceTokenCreateResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_service_token_endpoint_auth_service_tokens__token_id__revoke_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServiceTokenResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_auth_users_auth_users_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    create_auth_user_auth_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LocalUserCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocalUserResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_auth_user_auth_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LocalUserUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocalUserResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_auth_user_password_auth_users__user_id__password_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LocalUserPasswordResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LocalUserResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_category_overrides_categories_overrides_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOverridesResponse"];
                };
            };
        };
    };
    set_category_override_endpoint_categories_overrides__counterparty_name__put: {
        parameters: {
            query: {
                category: string;
            };
            header?: never;
            path: {
                counterparty_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOverrideRow"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_category_override_categories_overrides__counterparty_name__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                counterparty_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryOverrideDeleteResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_category_rules_categories_rules_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryRulesResponse"];
                };
            };
        };
    };
    create_category_rule_categories_rules_post: {
        parameters: {
            query: {
                rule_id: string;
                pattern: string;
                category: string;
                priority?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryRuleRow"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_category_rule_categories_rules__rule_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CategoryDeleteResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_column_mappings_config_column_mappings_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_column_mapping_config_column_mappings_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ColumnMappingRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_column_mapping_config_column_mappings_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ColumnMappingPreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_column_mapping_config_column_mappings__column_mapping_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                column_mapping_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_column_mapping_archived_state_config_column_mappings__column_mapping_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                column_mapping_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_column_mapping_diff_config_column_mappings__column_mapping_id__diff_get: {
        parameters: {
            query: {
                other_id: string;
            };
            header?: never;
            path: {
                column_mapping_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_dataset_contracts_config_dataset_contracts_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_dataset_contract_config_dataset_contracts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DatasetContractRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dataset_contract_config_dataset_contracts__dataset_contract_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dataset_contract_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_dataset_contract_archived_state_config_dataset_contracts__dataset_contract_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dataset_contract_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dataset_contract_diff_config_dataset_contracts__dataset_contract_id__diff_get: {
        parameters: {
            query: {
                other_id: string;
            };
            header?: never;
            path: {
                dataset_contract_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_execution_schedules_config_execution_schedules_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_execution_schedule_config_execution_schedules_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExecutionScheduleRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_execution_schedule_config_execution_schedules__schedule_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_execution_schedule_config_execution_schedules__schedule_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExecutionScheduleRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_execution_schedule_archived_state_config_execution_schedules__schedule_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                schedule_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_extension_registry_activations_config_extension_registry_activations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_extension_registry_revisions_config_extension_registry_revisions_get: {
        parameters: {
            query?: {
                extension_registry_source_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_extension_registry_revision_config_extension_registry_revisions__extension_registry_revision_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_registry_revision_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_extension_registry_sources_config_extension_registry_sources_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_extension_registry_source_config_extension_registry_sources_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExtensionRegistrySourceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_extension_registry_source_config_extension_registry_sources__extension_registry_source_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_registry_source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_extension_registry_source_config_extension_registry_sources__extension_registry_source_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_registry_source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExtensionRegistrySourceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    activate_extension_registry_source_config_extension_registry_sources__extension_registry_source_id__activate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_registry_source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExtensionRegistryActivationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_extension_registry_source_archived_state_config_extension_registry_sources__extension_registry_source_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_registry_source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sync_extension_registry_source_route_config_extension_registry_sources__extension_registry_source_id__sync_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_registry_source_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExtensionRegistrySyncRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_ingestion_definitions_config_ingestion_definitions_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_ingestion_definition_config_ingestion_definitions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IngestionDefinitionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_ingestion_definition_config_ingestion_definitions__ingestion_definition_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ingestion_definition_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_ingestion_definition_config_ingestion_definitions__ingestion_definition_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ingestion_definition_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IngestionDefinitionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_ingestion_definition_archived_state_config_ingestion_definitions__ingestion_definition_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ingestion_definition_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_publication_definitions_config_publication_definitions_get: {
        parameters: {
            query?: {
                transformation_package_id?: string | null;
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_publication_definition_config_publication_definitions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicationDefinitionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_publication_definition_config_publication_definitions__publication_definition_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                publication_definition_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicationDefinitionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_publication_definition_archived_state_config_publication_definitions__publication_definition_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                publication_definition_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_publication_keys_config_publication_keys_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_source_assets_config_source_assets_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_source_asset_config_source_assets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceAssetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_source_asset_config_source_assets__source_asset_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_asset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_source_asset_config_source_assets__source_asset_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_asset_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceAssetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_source_asset_archived_state_config_source_assets__source_asset_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_asset_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_source_systems_config_source_systems_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    create_source_system_config_source_systems_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceSystemRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_source_system_config_source_systems__source_system_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_system_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceSystemRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_transformation_handlers_config_transformation_handlers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_transformation_packages_config_transformation_packages_get: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_transformation_package_config_transformation_packages_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TransformationPackageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_transformation_package_config_transformation_packages__transformation_package_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                transformation_package_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TransformationPackageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_transformation_package_archived_state_config_transformation_packages__transformation_package_id__archive_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                transformation_package_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedStateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_publication_contracts_contracts_publications_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicationContractsResponse"];
                };
            };
        };
    };
    get_publication_contract_contracts_publications__publication_key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                publication_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicationContractModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_ui_descriptors_contracts_ui_descriptors_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UiDescriptorsResponse"];
                };
            };
        };
    };
    list_auth_audit_control_auth_audit_get: {
        parameters: {
            query?: {
                event_type?: string | null;
                success?: boolean | null;
                subject_username?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_operational_summary_control_operational_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_publication_audit_control_publication_audit_get: {
        parameters: {
            query?: {
                run_id?: string | null;
                publication_key?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_schedule_dispatches_control_schedule_dispatches_get: {
        parameters: {
            query?: {
                schedule_id?: string | null;
                status?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_schedule_dispatch_control_schedule_dispatches_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleDispatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_schedule_dispatch_control_schedule_dispatches__dispatch_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dispatch_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_schedule_dispatch_control_schedule_dispatches__dispatch_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dispatch_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleDispatchResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_source_freshness_control_source_freshness_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_source_lineage_control_source_lineage_get: {
        parameters: {
            query?: {
                run_id?: string | null;
                target_layer?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_terminal_commands_control_terminal_commands_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TerminalCommandsResponseModel"];
                };
            };
        };
    };
    execute_terminal_command_endpoint_control_terminal_execute_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TerminalExecutionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TerminalExecutionResponseModel"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TerminalExecutionResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TerminalExecutionResponseModel"];
                };
            };
        };
    };
    list_extensions_extensions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_functions_functions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    ingest_account_transactions_ingest_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    ingest_account_transactions_alias_ingest_account_transactions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    ingest_configured_csv_ingest_configured_csv_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    ingest_contract_prices_ingest_contract_prices_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    process_ingestion_definition_ingest_ingestion_definitions__ingestion_definition_id__process_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ingestion_definition_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConfiguredIngestionProcessResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_subscriptions_ingest_subscriptions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    run_landing_extension_landing__extension_key__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                extension_key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metrics_metrics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    ready_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_account_balance_trend_reports_account_balance_trend_get: {
        parameters: {
            query?: {
                account_id?: string | null;
                from_month?: string | null;
                to_month?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountBalanceTrendResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_affordability_ratios_reports_affordability_ratios_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AffordabilityRatiosResponse"];
                };
            };
        };
    };
    get_attention_items_reports_attention_items_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AttentionItemsResponse"];
                };
            };
        };
    };
    get_budget_progress_reports_budget_progress_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BudgetProgressResponse"];
                };
            };
        };
    };
    get_budget_variance_reports_budget_variance_get: {
        parameters: {
            query?: {
                budget_name?: string | null;
                category_id?: string | null;
                period_label?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BudgetVarianceResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_contract_price_current_reports_contract_prices_get: {
        parameters: {
            query?: {
                contract_type?: string | null;
                status?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContractPriceCurrentResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_contract_renewal_watchlist_reports_contract_renewal_watchlist_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContractRenewalWatchlistResponse"];
                };
            };
        };
    };
    get_contract_review_candidates_reports_contract_review_candidates_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContractReviewCandidatesResponse"];
                };
            };
        };
    };
    get_cost_trend_reports_cost_trend_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CostTrendResponse"];
                };
            };
        };
    };
    get_current_dimension_report_reports_current_dimensions__dimension_name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dimension_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CurrentDimensionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_electricity_price_current_reports_electricity_prices_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ElectricityPriceCurrentResponse"];
                };
            };
        };
    };
    get_household_cost_model_reports_household_cost_model_get: {
        parameters: {
            query?: {
                period_label?: string | null;
                cost_type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HouseholdCostModelResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_household_overview_reports_household_overview_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HouseholdOverviewResponse"];
                };
            };
        };
    };
    get_loan_overview_reports_loan_overview_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoanOverviewResponse"];
                };
            };
        };
    };
    get_loan_schedule_reports_loan_schedule__loan_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                loan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoanScheduleResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_loan_variance_reports_loan_variance_get: {
        parameters: {
            query?: {
                loan_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoanVarianceResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_monthly_cashflow_reports_monthly_cashflow_get: {
        parameters: {
            query?: {
                from_month?: string | null;
                to_month?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MonthlyCashflowResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_monthly_cashflow_by_counterparty_reports_monthly_cashflow_by_counterparty_get: {
        parameters: {
            query?: {
                from_month?: string | null;
                to_month?: string | null;
                counterparty?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MonthlyCashflowByCounterpartyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_operating_baseline_reports_operating_baseline_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperatingBaselineResponse"];
                };
            };
        };
    };
    get_recent_changes_reports_recent_changes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecentChangesResponse"];
                };
            };
        };
    };
    get_recent_large_transactions_reports_recent_large_transactions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecentLargeTransactionsResponse"];
                };
            };
        };
    };
    get_recurring_cost_baseline_reports_recurring_cost_baseline_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecurringCostBaselineResponse"];
                };
            };
        };
    };
    get_spend_by_category_monthly_reports_spend_by_category_monthly_get: {
        parameters: {
            query?: {
                from_month?: string | null;
                to_month?: string | null;
                counterparty?: string | null;
                category?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SpendByCategoryMonthlyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_subscription_summary_reports_subscription_summary_get: {
        parameters: {
            query?: {
                status?: string | null;
                currency?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubscriptionSummaryResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_transaction_anomalies_reports_transaction_anomalies_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TransactionAnomaliesResponse"];
                };
            };
        };
    };
    get_upcoming_fixed_costs_reports_upcoming_fixed_costs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UpcomingFixedCostsResponse"];
                };
            };
        };
    };
    get_usage_vs_price_reports_usage_vs_price_get: {
        parameters: {
            query?: {
                utility_type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsageVsPriceResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_utility_cost_summary_reports_utility_cost_summary_get: {
        parameters: {
            query?: {
                utility_type?: string | null;
                meter_id?: string | null;
                from_period?: string | null;
                to_period?: string | null;
                granularity?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UtilityCostSummaryResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_utility_cost_trend_reports_utility_cost_trend_get: {
        parameters: {
            query?: {
                utility_type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UtilityCostTrendResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_reporting_extension_reports__extension_key__get: {
        parameters: {
            query?: {
                run_id?: string | null;
            };
            header?: never;
            path: {
                extension_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExtensionReportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_runs_runs_get: {
        parameters: {
            query?: {
                dataset?: string | null;
                status?: string | null;
                from_date?: string | null;
                to_date?: string | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_run_runs__run_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunMutationResponseModel"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sources_sources_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_transformation_audit_transformation_audit_get: {
        parameters: {
            query?: {
                run_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TransformationAuditResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_transformation_extension_transformations__extension_key__get: {
        parameters: {
            query?: {
                run_id?: string | null;
            };
            header?: never;
            path: {
                extension_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}

