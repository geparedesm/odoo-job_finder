import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("job_finder_application_tour", {
    steps: () => [
        {
            trigger: ".o_list_view button[name='action_open_application_form']",
            run: "click",
        },
        {
            trigger: ".o_form_view .o_field_widget[name='company'] input",
            run: "edit Tour company",
        },
        {
            trigger: ".o_field_widget[name='position'] input",
            run: "edit Tour developer",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_form_view:not(:has(.o_form_status_indicator_new_record)) .o_field_widget[name='company'] input",
        },
        {
            trigger: ".o_breadcrumb .breadcrumb-item a",
            run: "click",
        },
        {
            trigger: ".o_data_row:contains('Tour company')",
        },
        {
            trigger: ".o_searchview_dropdown_toggler",
            run: "click",
        },
        {
            trigger: ".o_filter_menu .o_menu_item:contains('Sent')",
            run: "click",
        },
        {
            trigger: ".o_searchview_facet:contains('Sent')",
        },
        {
            trigger: ".o_data_row:contains('Tour company')",
        },
    ],
});
