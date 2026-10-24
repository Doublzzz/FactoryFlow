/** Generated from contracts/openapi.json. Do not edit. */
export interface paths {
    "/api/v1/archive-settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Settings */
        get: operations["getArchiveSettings"];
        put?: never;
        /** Save Settings */
        post: operations["saveArchiveSettings"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/archive-sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sources */
        get: operations["listArchiveSources"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/archives": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listing */
        get: operations["listArchives"];
        put?: never;
        /** Create */
        post: operations["createArchive"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/archives/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["previewArchive"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/archives/{identifier}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["getArchive"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/archives/{identifier}/file": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download */
        get: operations["downloadArchive"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/archives/{identifier}/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate */
        post: operations["generateArchive"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Session */
        get: operations["getSession"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/customers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Customers */
        get: operations["listCustomers"];
        put?: never;
        /** Create Customer */
        post: operations["createCustomer"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/customers/{customer_id}/statement-settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["getStatementSettings"];
        put?: never;
        /** Save Settings */
        post: operations["saveStatementSettings"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/customers/{customer_id}/statement-templates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listing */
        get: operations["listStatementTemplates"];
        put?: never;
        /** Import Template */
        post: operations["importStatementTemplate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/customers/{customer_id}/statement-templates/inspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Inspect */
        post: operations["inspectStatementTemplate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/customers/{customer_id}/statement-templates/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["previewStatementTemplate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/customers/{customer_id}/statement-templates/{template_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["getStatementTemplate"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/deliveries": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Deliveries */
        get: operations["listDeliveries"];
        put?: never;
        /** Create */
        post: operations["createDelivery"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/deliveries/{delivery_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["getDelivery"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/deliveries/{delivery_id}/print": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Print Delivery */
        get: operations["printDelivery"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/deliveries/{delivery_id}/void": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Void */
        post: operations["voidDelivery"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/delivery-layout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Layout */
        get: operations["getDeliveryLayout"];
        put?: never;
        /** Save Layout */
        post: operations["saveDeliveryLayout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/delivery-layout/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Layout */
        post: operations["previewDeliveryLayout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{revision_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Evidence */
        get: operations["getEvidence"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/documents/{revision_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Evidence */
        get: operations["downloadEvidence"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/extractions/{extraction_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Extraction */
        get: operations["getExtraction"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/extractions/{extraction_id}/pages/{number}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preview */
        get: operations["getSourcePage"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Liveness
         * @description Process liveness only; this does not verify business storage readiness.
         */
        get: operations["getLiveness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Readiness */
        get: operations["getReadiness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/material-codes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Codes */
        get: operations["listMaterialCodes"];
        put?: never;
        /** Save Code */
        post: operations["saveMaterialCode"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/materials": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Materials */
        get: operations["listMaterials"];
        put?: never;
        /** Create Material */
        post: operations["createMaterial"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/materials/imports/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm Material Import */
        post: operations["confirmMaterialImport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/materials/imports/inspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Inspect Material Import */
        post: operations["inspectMaterialImport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/materials/imports/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Material Import */
        post: operations["previewMaterialImport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/materials/{material_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Update Material */
        post: operations["updateMaterial"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm Order */
        post: operations["confirmOrder"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/open-lines": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Open Lines */
        get: operations["listOpenLines"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Order */
        post: operations["previewOrder"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Order */
        get: operations["getOrder"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}/delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Delete Order */
        post: operations["deleteOrder"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}/material-links": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Link Order Materials */
        post: operations["linkOrderMaterials"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Restore Order */
        post: operations["restoreOrder"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/orders/{order_id}/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revise Order */
        post: operations["reviseOrder"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sources */
        get: operations["listSources"];
        put?: never;
        /** Upload Source */
        post: operations["uploadSource"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources/{source_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Original */
        get: operations["downloadSource"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources/{source_id}/extractions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Extract */
        post: operations["extractSource"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-approvals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Approvals */
        get: operations["listStatementApprovals"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-approvals/{approval_id}/correct": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correct Approval */
        post: operations["correctStatementApproval"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-approvals/{approval_id}/correct-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correct Approval Preview */
        post: operations["previewApprovalCorrection"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-approvals/{approval_id}/defer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Defer */
        post: operations["deferStatementApproval"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-approvals/{approval_id}/defer-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Defer Preview */
        post: operations["previewStatementDefer"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Candidates */
        get: operations["getStatementCandidates"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-evidence/{evidence_id}/file": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Evidence File */
        get: operations["downloadStatementEvidence"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-exports/{export_id}/file": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Export */
        get: operations["downloadStatementExport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-exports/{export_id}/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate Export */
        post: operations["generateStatementExport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statement-reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Reviews */
        get: operations["listStatementReviews"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listing */
        get: operations["listStatementDrafts"];
        put?: never;
        /** Create */
        post: operations["createStatementDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["getStatementDraft"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/abandon": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Abandon */
        post: operations["abandonStatementDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve */
        post: operations["approveStatementQuantity"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/claim-review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Claim Review */
        post: operations["claimStatementReview"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/correct": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correct Settlement */
        post: operations["correctStatementSettlement"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/correction-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correction Preview */
        post: operations["previewSettlementCorrection"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Exports */
        get: operations["listStatementExports"];
        put?: never;
        /** Create Export */
        post: operations["createStatementExport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Feedback */
        post: operations["recordStatementFeedback"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/lifecycle": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** View */
        get: operations["getStatementLifecycle"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/release": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Release */
        post: operations["releaseStatementAllocation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/reopen": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reopen */
        post: operations["reopenStatementDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/reserve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reserve */
        post: operations["reserveStatementApproval"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Review */
        post: operations["reviewStatementQuantity"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/save": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Save */
        post: operations["saveStatementDraft"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/sent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sent */
        post: operations["recordStatementSent"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/settle": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Settle */
        post: operations["settleStatement"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/settlement-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview */
        post: operations["previewStatementSettlement"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/statements/{statement_id}/void": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Void Statement */
        post: operations["voidStatementDraft"];
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
        /** AbandonDraftInput */
        AbandonDraftInput: {
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
        };
        /** AdjustmentInput */
        AdjustmentInput: {
            /** Amount */
            amount: string;
            /** Delivery Id */
            delivery_id?: string | null;
            /** Kind */
            kind: string;
            /** Order Line Id */
            order_line_id?: string | null;
            /** Reason */
            reason: string;
            /**
             * Stage
             * @enum {string}
             */
            stage: "before_tax" | "after_tax";
        };
        /** ApprovalPage */
        ApprovalPage: {
            /** Items */
            items: components["schemas"]["StatementApproval"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** ApproveInput */
        ApproveInput: {
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /** Expected Version */
            expected_version: number;
            /**
             * Feedback Id
             * Format: uuid
             */
            feedback_id: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /**
             * Sent Id
             * Format: uuid
             */
            sent_id: string;
            /** Target End */
            target_end: string;
            /** Target Start */
            target_start: string;
            /** Unit Price */
            unit_price: string;
        };
        /** ArchiveBatch */
        ArchiveBatch: {
            /** Created At */
            created_at: string;
            /** Current */
            current: boolean;
            /** Error Code */
            error_code: string | null;
            /** File Hash */
            file_hash: string | null;
            /** Id */
            id: string;
            /** Items */
            items: components["schemas"]["ArchiveItem"][];
            /** Local Available */
            local_available: boolean | null;
            /** Local Error */
            local_error: string | null;
            /** Relative Directory */
            relative_directory: string;
            /**
             * Rule
             * @enum {string}
             */
            rule: "date" | "customer" | "month_customer";
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "failed" | "ready";
            /** Total Bytes */
            total_bytes: number;
        };
        /** ArchiveBatches */
        ArchiveBatches: {
            /** Items */
            items: components["schemas"]["ArchiveBatch"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** ArchiveCreateRequest */
        ArchiveCreateRequest: {
            /** Preview Token */
            preview_token: string;
            /**
             * Rule
             * @enum {string}
             */
            rule: "date" | "customer" | "month_customer";
            /** Selections */
            selections: components["schemas"]["ArchiveSelection"][];
        };
        /** ArchiveItem */
        ArchiveItem: {
            /** Available */
            available: boolean;
            /** Business Date */
            business_date: string | null;
            /** Byte Size */
            byte_size: number;
            /** Current */
            current: boolean;
            /** Customer Id */
            customer_id: string | null;
            /** Customer Name */
            customer_name: string | null;
            /** Extension */
            extension: string;
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "source" | "delivery" | "statement_export";
            /** Path */
            path: string;
            /** Period End */
            period_end: string | null;
            /** Sha256 */
            sha256: string;
            /** Source Id */
            source_id: string;
            /** State Label */
            state_label: string;
            /** Title */
            title: string;
            /** Token */
            token: string;
            /** Version Label */
            version_label: string;
        };
        /** ArchivePreview */
        ArchivePreview: {
            /** Items */
            items: components["schemas"]["ArchiveItem"][];
            /** Preview Token */
            preview_token: string;
            /** Total Bytes */
            total_bytes: number;
        };
        /** ArchivePreviewRequest */
        ArchivePreviewRequest: {
            /**
             * Rule
             * @enum {string}
             */
            rule: "date" | "customer" | "month_customer";
            /** Selections */
            selections: components["schemas"]["ArchiveSelection"][];
        };
        /** ArchiveSelection */
        ArchiveSelection: {
            /** Key */
            key: string;
            /** Token */
            token: string;
        };
        /** ArchiveSettings */
        ArchiveSettings: {
            /** Root Configured */
            root_configured: boolean;
            /**
             * Rule
             * @enum {string}
             */
            rule: "date" | "customer" | "month_customer";
            /** Updated At */
            updated_at: string | null;
            /** Version */
            version: number;
        };
        /** ArchiveSource */
        ArchiveSource: {
            /** Available */
            available: boolean;
            /** Business Date */
            business_date: string | null;
            /** Byte Size */
            byte_size: number | null;
            /** Current */
            current: boolean;
            /** Customer Id */
            customer_id: string | null;
            /** Customer Name */
            customer_name: string | null;
            /** Extension */
            extension: string;
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "source" | "delivery" | "statement_export";
            /** Period End */
            period_end: string | null;
            /** Source Id */
            source_id: string;
            /** State Label */
            state_label: string;
            /** Title */
            title: string;
            /** Token */
            token: string;
            /** Version Label */
            version_label: string;
        };
        /** ArchiveSources */
        ArchiveSources: {
            /** Items */
            items: components["schemas"]["ArchiveSource"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** Candidate */
        Candidate: {
            /** Business Date */
            business_date: string;
            /** Currency */
            currency: string;
            /** Lines */
            lines: components["schemas"]["CandidateLine"][];
            /** Order Number */
            order_number: string;
            /** Warnings */
            warnings?: components["schemas"]["CandidateWarning"][];
        };
        /** CandidateLine */
        CandidateLine: {
            /** Description */
            description: string;
            /** Item Code */
            item_code?: string | null;
            /** Item Name */
            item_name?: string | null;
            /** Quantity */
            quantity: string;
            /** Source Amount */
            source_amount: string | null;
            /** Source Unit Price */
            source_unit_price: string | null;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit: string | null;
        };
        /** CandidateWarning */
        CandidateWarning: {
            /**
             * Code
             * @constant
             */
            code: "TABLE_COVERAGE_UNRESOLVED";
            /** Page */
            page: number;
        };
        /** ClaimReviewInput */
        ClaimReviewInput: {
            /** Expected Version */
            expected_version: number;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /**
             * Review Id
             * Format: uuid
             */
            review_id: string;
            /** Review Version */
            review_version: number;
            /** Unit Price */
            unit_price: string;
        };
        /** CorrectApprovalInput */
        CorrectApprovalInput: {
            /**
             * Cause
             * @enum {string}
             */
            cause: "entry_error" | "customer_change";
            /**
             * Disposition
             * @constant
             */
            disposition: "review";
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Expected Version */
            expected_version: number;
            /** Preview Token */
            preview_token: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Unit Price */
            unit_price: string;
        };
        /** CorrectApprovalPreviewInput */
        CorrectApprovalPreviewInput: {
            /**
             * Cause
             * @enum {string}
             */
            cause: "entry_error" | "customer_change";
            /**
             * Disposition
             * @constant
             */
            disposition: "review";
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Expected Version */
            expected_version: number;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Unit Price */
            unit_price: string;
        };
        /** CorrectSettlementInput */
        CorrectSettlementInput: {
            /**
             * Allocation Id
             * Format: uuid
             */
            allocation_id: string;
            /**
             * Cause
             * @enum {string}
             */
            cause: "entry_error" | "customer_change" | "return";
            /**
             * Disposition
             * @enum {string}
             */
            disposition: "review" | "pending";
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Expected Version */
            expected_version: number;
            /** No Downstream Effects */
            no_downstream_effects: boolean;
            /** Preview Token */
            preview_token: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Unit Price */
            unit_price: string;
        };
        /** CorrectSettlementPreviewInput */
        CorrectSettlementPreviewInput: {
            /**
             * Allocation Id
             * Format: uuid
             */
            allocation_id: string;
            /**
             * Cause
             * @enum {string}
             */
            cause: "entry_error" | "customer_change" | "return";
            /**
             * Disposition
             * @enum {string}
             */
            disposition: "review" | "pending";
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** Expected Version */
            expected_version: number;
            /** No Downstream Effects */
            no_downstream_effects: boolean;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Unit Price */
            unit_price: string;
        };
        /** CustomerInput */
        CustomerInput: {
            /** Full Name */
            full_name: string;
        };
        /** CustomerResponse */
        CustomerResponse: {
            /** Full Name */
            full_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** DeferInput */
        DeferInput: {
            /** Expected Version */
            expected_version: number;
            /** Preview Token */
            preview_token: string;
            /** Reason */
            reason: string;
            /** Target End */
            target_end: string;
            /** Target Start */
            target_start: string;
        };
        /** DeferPreviewInput */
        DeferPreviewInput: {
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
            /** Target End */
            target_end: string;
            /** Target Start */
            target_start: string;
        };
        /** DeliveryDetail */
        DeliveryDetail: {
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Customer Name */
            customer_name: string;
            /** Delivery Date */
            delivery_date: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lines */
            lines: components["schemas"]["DeliveryLine"][];
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /** Order Number */
            order_number: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "void";
            /** Version */
            version: number;
            /** Void Reason */
            void_reason: string | null;
            /** Voided At */
            voided_at: string | null;
        };
        /** DeliveryInput */
        DeliveryInput: {
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Delivery Date */
            delivery_date: string;
            /** Expected Version */
            expected_version: number;
            /** Lines */
            lines: components["schemas"]["DeliveryLineInput"][];
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
        };
        /** DeliveryLayoutColumn */
        DeliveryLayoutColumn: {
            /**
             * Key
             * @enum {string}
             */
            key: "index" | "order_number" | "item_code" | "specification" | "unit" | "quantity" | "note";
            /** Label */
            label: string;
            /** Width Mm */
            width_mm: number;
        };
        /** DeliveryLayoutConfig */
        DeliveryLayoutConfig: {
            /** Address */
            address: string;
            /** Columns */
            columns: components["schemas"]["DeliveryLayoutColumn"][];
            /** Company Name */
            company_name: string;
            /** Delivery Person */
            delivery_person: string;
            /** Fax */
            fax: string;
            /** Font Size Pt */
            font_size_pt: number;
            /** Footer Note */
            footer_note: string;
            /** Margin Bottom Mm */
            margin_bottom_mm: number;
            /** Margin Left Mm */
            margin_left_mm: number;
            /** Margin Right Mm */
            margin_right_mm: number;
            /** Margin Top Mm */
            margin_top_mm: number;
            /** Paper Height Mm */
            paper_height_mm: number;
            /** Paper Width Mm */
            paper_width_mm: number;
            /** Phone */
            phone: string;
            /** Postcode */
            postcode: string;
            /** Row Height Mm */
            row_height_mm: number;
            /** Rows Per Page */
            rows_per_page: number;
            /** Signatures */
            signatures: string[];
            /** Title */
            title: string;
            /** Title Size Pt */
            title_size_pt: number;
        };
        /** DeliveryLayoutDetail */
        DeliveryLayoutDetail: {
            config: components["schemas"]["DeliveryLayoutConfig"];
            defaults: components["schemas"]["DeliveryLayoutConfig"];
            /** Updated At */
            updated_at: string | null;
            /** Version */
            version: number;
        };
        /** DeliveryLine */
        DeliveryLine: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /** Description */
            description: string;
            /** Line Number */
            line_number: number;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            quantity_policy: components["schemas"]["DeliveryPolicy"];
            /** Source Unit */
            source_unit: string | null;
        };
        /** DeliveryLineInput */
        DeliveryLineInput: {
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
        };
        /** DeliveryPage */
        DeliveryPage: {
            /** Items */
            items: components["schemas"]["DeliverySummary"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** DeliveryPolicy */
        DeliveryPolicy: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /**
             * Mode
             * @enum {string}
             */
            mode: "INTEGER_ONLY" | "DECIMAL_ALLOWED" | "UNKNOWN";
            /** Version */
            version: string;
            /** Warning Codes */
            warning_codes: string[];
        };
        /** DeliverySummary */
        DeliverySummary: {
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Customer Name */
            customer_name: string;
            /** Delivery Date */
            delivery_date: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /** Order Number */
            order_number: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "void";
            /** Version */
            version: number;
            /** Void Reason */
            void_reason: string | null;
            /** Voided At */
            voided_at: string | null;
        };
        /** DraftInput */
        DraftInput: {
            /** Adjustments */
            adjustments?: components["schemas"]["AdjustmentInput"][];
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Lines */
            lines?: components["schemas"]["StatementLineInput"][];
            /** Period End */
            period_end: string;
            /** Period Start */
            period_start: string;
            /**
             * Reason
             * @default
             */
            reason: string;
            /**
             * Tax Mode
             * @enum {string}
             */
            tax_mode: "included" | "untaxed_final" | "add_tax";
            /** Tax Rate */
            tax_rate: string;
        };
        /** ErrorResponse */
        ErrorResponse: {
            /** Code */
            code: string;
            /** Field */
            field?: string | null;
            /** Message */
            message: string;
            /** Request Id */
            request_id: string;
        };
        /** EvidenceContent */
        EvidenceContent: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Confirmed At */
            confirmed_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            order: components["schemas"]["EvidenceOrder"];
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            /** Parent Revision Id */
            parent_revision_id: string | null;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Revision Number */
            revision_number: number;
            /** Schema Version */
            schema_version: number;
            source?: components["schemas"]["EvidenceSource"] | null;
        };
        /** EvidenceLine */
        EvidenceLine: {
            /** Canonical Quantity */
            canonical_quantity: string;
            /** Description */
            description: string;
            /** Item Code */
            item_code?: string | null;
            /** Item Name */
            item_name?: string | null;
            /** Line Number */
            line_number: number;
            quantity_policy: components["schemas"]["QuantityPolicy"];
            /** Source Amount */
            source_amount: string | null;
            /** Source Quantity Text */
            source_quantity_text: string;
            /** Source Unit */
            source_unit: string | null;
            /** Source Unit Price */
            source_unit_price: string | null;
            /** Specification */
            specification?: string | null;
        };
        /** EvidenceOrder */
        EvidenceOrder: {
            /** Business Date */
            business_date: string;
            /** Currency */
            currency: string;
            /** Lines */
            lines: components["schemas"]["EvidenceLine"][];
            /** Order Number */
            order_number: string;
        };
        /** EvidenceResponse */
        EvidenceResponse: {
            content: components["schemas"]["EvidenceContent"];
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Sha256 */
            sha256: string;
        };
        /** EvidenceSource */
        EvidenceSource: {
            /**
             * Extraction Id
             * Format: uuid
             */
            extraction_id: string;
            /** Original Sha256 */
            original_sha256: string;
            /** Source Hash */
            source_hash: string;
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
            /** Trace Hash */
            trace_hash: string;
        };
        /** ExtractionDetail */
        ExtractionDetail: {
            candidate: components["schemas"]["Candidate"];
            /** Error Code */
            error_code: string | null;
            /**
             * Extraction Id
             * Format: uuid
             */
            extraction_id: string;
            /** Original Sha256 */
            original_sha256: string;
            /** Pages */
            pages: components["schemas"]["ExtractionPage"][];
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "failed";
            /** Trace Hash */
            trace_hash: string;
        };
        /** ExtractionPage */
        ExtractionPage: {
            /** Height */
            height: number;
            /** Number */
            number: number;
            /** Rows */
            rows: string[];
            /** Text */
            text: string;
            /** Width */
            width: number;
        };
        /** ExtractionResult */
        ExtractionResult: {
            /**
             * Extraction Id
             * Format: uuid
             */
            extraction_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "failed";
        };
        /** FeedbackInput */
        FeedbackInput: {
            /** Content Base64 */
            content_base64?: string | null;
            /** Filename */
            filename?: string | null;
            /** Media Type */
            media_type?: ("application/pdf" | "image/png" | "image/jpeg") | null;
            /**
             * Note
             * @default
             */
            note: string;
            /** Occurred On */
            occurred_on: string;
            /** Person */
            person: string;
        };
        /** LifecycleHistory */
        LifecycleHistory: {
            /** Created At */
            created_at: string;
            /**
             * Entity Id
             * Format: uuid
             */
            entity_id: string;
            /** Kind */
            kind: string;
            /** Snapshot */
            snapshot: {
                [key: string]: unknown;
            };
            /** Version */
            version: number;
        };
        /** LifecyclePreview */
        LifecyclePreview: {
            /** Affected Allocations */
            affected_allocations: components["schemas"]["StatementAllocation"][];
            /** Blockers */
            blockers: string[];
            calculation: components["schemas"]["StatementCalculation"] | null;
            /** Token */
            token: string;
        };
        /** Liveness */
        Liveness: {
            /**
             * Service
             * @default FactoryFlow
             * @constant
             */
            service: "FactoryFlow";
            /**
             * Status
             * @default ok
             * @constant
             */
            status: "ok";
            /**
             * Version
             * @default 0.1.0
             */
            version: string;
        };
        /** LoginInput */
        LoginInput: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** MatchedCustomerCode */
        MatchedCustomerCode: {
            /** Customer Code */
            customer_code: string;
            /** Customer Name */
            customer_name: string;
        };
        /** MaterialCodeInput */
        MaterialCodeInput: {
            /** Customer Code */
            customer_code: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /**
             * Expected Mapping Version
             * @default 0
             */
            expected_mapping_version: number;
            /** Expected Material Version */
            expected_material_version: number;
            /** Item Name */
            item_name?: string | null;
            /**
             * Material Id
             * Format: uuid
             */
            material_id: string;
            /** Reason */
            reason?: string | null;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit?: string | null;
        };
        /** MaterialCodeList */
        MaterialCodeList: {
            /** Items */
            items: components["schemas"]["MaterialCodeResponse"][];
        };
        /** MaterialCodeResponse */
        MaterialCodeResponse: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /** Change */
            change?: {
                [key: string]: unknown;
            } | null;
            /** Customer Code */
            customer_code: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Item Name */
            item_name: string | null;
            /**
             * Material Id
             * Format: uuid
             */
            material_id: string;
            /** Specification */
            specification: string | null;
            /** Version */
            version: number;
        };
        /** MaterialImportChoice */
        MaterialImportChoice: {
            /**
             * Action
             * @enum {string}
             */
            action: "default" | "create" | "reuse" | "skip";
            /** Confirmed Numeric Fields */
            confirmed_numeric_fields?: ("own_code" | "customer_code")[];
            /** Expected Material Version */
            expected_material_version?: number | null;
            /** Material Id */
            material_id?: string | null;
            /** Row Number */
            row_number: number;
        };
        /** MaterialImportColumn */
        MaterialImportColumn: {
            /** Index */
            index: number;
            /** Label */
            label: string;
        };
        /** MaterialImportColumns */
        MaterialImportColumns: {
            /** Customer Code */
            customer_code?: number | null;
            /** Name */
            name: number;
            /** Own Code */
            own_code?: number | null;
            /** Specification */
            specification?: number | null;
            /** Unit */
            unit?: number | null;
        };
        /** MaterialImportConfirm */
        MaterialImportConfirm: {
            /** Choices */
            choices?: components["schemas"]["MaterialImportChoice"][];
            columns: components["schemas"]["MaterialImportColumns"];
            /** Content Base64 */
            content_base64: string;
            /** Customer Id */
            customer_id?: string | null;
            /** Filename */
            filename: string;
            /**
             * Header Row
             * @default 1
             */
            header_row: number;
            /** Preview Fingerprint */
            preview_fingerprint: string;
        };
        /** MaterialImportFile */
        MaterialImportFile: {
            /** Content Base64 */
            content_base64: string;
            /** Filename */
            filename: string;
            /**
             * Header Row
             * @default 1
             */
            header_row: number;
        };
        /** MaterialImportInput */
        MaterialImportInput: {
            /** Choices */
            choices?: components["schemas"]["MaterialImportChoice"][];
            columns: components["schemas"]["MaterialImportColumns"];
            /** Content Base64 */
            content_base64: string;
            /** Customer Id */
            customer_id?: string | null;
            /** Filename */
            filename: string;
            /**
             * Header Row
             * @default 1
             */
            header_row: number;
        };
        /** MaterialImportInspection */
        MaterialImportInspection: {
            /** Columns */
            columns: components["schemas"]["MaterialImportColumn"][];
            /** Data Row Count */
            data_row_count: number;
            /** File Hash */
            file_hash: string;
            /** Header Row */
            header_row: number;
            /** Samples */
            samples: components["schemas"]["MaterialImportSample"][];
            /** Sheet Name */
            sheet_name: string;
        };
        /** MaterialImportNumeric */
        MaterialImportNumeric: {
            /**
             * Field
             * @enum {string}
             */
            field: "own_code" | "customer_code";
            /** Number Format */
            number_format: string | null;
            /** Value */
            value: string;
        };
        /** MaterialImportPreview */
        MaterialImportPreview: {
            /** File Hash */
            file_hash: string;
            /** Preview Fingerprint */
            preview_fingerprint: string;
            /** Ready */
            ready: boolean;
            /** Rows */
            rows: components["schemas"]["MaterialImportPreviewRow"][];
        };
        /** MaterialImportPreviewRow */
        MaterialImportPreviewRow: {
            /**
             * Action
             * @enum {string}
             */
            action: "create" | "reuse" | "skip" | "pending";
            /** Candidates */
            candidates: components["schemas"]["MaterialResponse"][];
            /** Issues */
            issues: string[];
            material: components["schemas"]["MaterialResponse"] | null;
            /** Numeric Fields */
            numeric_fields: components["schemas"]["MaterialImportNumeric"][];
            /** Row Number */
            row_number: number;
            source: components["schemas"]["MaterialImportValues"];
            /** Warnings */
            warnings: string[];
        };
        /** MaterialImportResult */
        MaterialImportResult: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Created Count */
            created_count: number;
            /** File Hash */
            file_hash: string;
            /** Mapping Count */
            mapping_count: number;
            /** Occurred At */
            occurred_at: string;
            /** Reused Count */
            reused_count: number;
            /** Rows */
            rows: components["schemas"]["MaterialImportResultRow"][];
            /** Skipped Count */
            skipped_count: number;
        };
        /** MaterialImportResultRow */
        MaterialImportResultRow: {
            /**
             * Action
             * @enum {string}
             */
            action: "create" | "reuse" | "skip";
            /** Change */
            change: {
                [key: string]: unknown;
            } | null;
            /** Mapping Change */
            mapping_change: {
                [key: string]: unknown;
            } | null;
            material: components["schemas"]["MaterialResponse"] | null;
            /** Reason */
            reason: string | null;
            /** Row Number */
            row_number: number;
        };
        /** MaterialImportSample */
        MaterialImportSample: {
            /** Row Number */
            row_number: number;
            /** Values */
            values: string[];
        };
        /** MaterialImportValues */
        MaterialImportValues: {
            /** Customer Code */
            customer_code: string | null;
            /** Name */
            name: string;
            /** Own Code */
            own_code: string | null;
            /** Specification */
            specification: string | null;
            /** Unit */
            unit: string | null;
        };
        /** MaterialInput */
        MaterialInput: {
            /** Name */
            name: string;
            /** Own Code */
            own_code?: string | null;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit?: string | null;
        };
        /** MaterialList */
        MaterialList: {
            /** Items */
            items: components["schemas"]["MaterialResponse"][];
            /** Next Offset */
            next_offset: number | null;
        };
        /** MaterialMappingChoice */
        MaterialMappingChoice: {
            /** Customer Code */
            customer_code: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Expected Mapping Version */
            expected_mapping_version: number;
        };
        /** MaterialResponse */
        MaterialResponse: {
            /** Active */
            active: boolean;
            /** Change */
            change?: {
                [key: string]: unknown;
            } | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Matched Customer Codes */
            matched_customer_codes?: components["schemas"]["MatchedCustomerCode"][];
            /** Name */
            name: string;
            /** Own Code */
            own_code: string;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit?: string | null;
            /** Version */
            version: number;
        };
        /** MaterialUpdate */
        MaterialUpdate: {
            /** Active */
            active: boolean;
            /** Expected Version */
            expected_version: number;
            /** Name */
            name: string;
            /** Own Code */
            own_code?: string | null;
            /** Reason */
            reason: string;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit?: string | null;
        };
        /** OpenLine */
        OpenLine: {
            /** Business Date */
            business_date: string;
            /** Canonical Unit */
            canonical_unit: string | null;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Customer Name */
            customer_name: string;
            /** Delivered Quantity */
            delivered_quantity: string;
            /** Description */
            description: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Item Code */
            item_code?: string | null;
            /** Item Name */
            item_name?: string | null;
            /** Line Number */
            line_number: number;
            material?: components["schemas"]["OrderMaterialSummary"] | null;
            /** Material Id */
            material_id?: string | null;
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /** Order Number */
            order_number: string;
            /** Quantity */
            quantity: string;
            quantity_policy: components["schemas"]["QuantityPolicy"];
            /** Remaining Quantity */
            remaining_quantity: string;
            /** Source Amount */
            source_amount: string | null;
            /** Source Quantity Text */
            source_quantity_text: string;
            /** Source Unit */
            source_unit: string | null;
            /** Source Unit Price */
            source_unit_price: string | null;
            /** Specification */
            specification?: string | null;
            /** Version */
            version: number;
        };
        /** OpenLinesResponse */
        OpenLinesResponse: {
            /** Items */
            items: components["schemas"]["OpenLine"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** OrderDetail */
        OrderDetail: {
            /** Business Date */
            business_date: string;
            /** Currency */
            currency: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Customer Name */
            customer_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lines */
            lines: components["schemas"]["OrderLineResponse"][];
            /** Order Number */
            order_number: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Revisions */
            revisions: components["schemas"]["RevisionSummary"][];
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "deleted";
            /** Version */
            version: number;
        };
        /** OrderInput */
        OrderInput: {
            /** Business Date */
            business_date: string;
            /**
             * Currency
             * @constant
             */
            currency: "CNY";
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Extraction Id */
            extraction_id?: string | null;
            /** Lines */
            lines: components["schemas"]["OrderLineInput"][];
            /** Material Choices */
            material_choices?: components["schemas"]["OrderMaterialChoice"][];
            /** Order Number */
            order_number: string;
        };
        /** OrderLineInput */
        OrderLineInput: {
            /**
             * Description
             * @default
             */
            description: string;
            /** Item Code */
            item_code?: string | null;
            /** Item Name */
            item_name?: string | null;
            /** Quantity */
            quantity: string;
            /** Source Amount */
            source_amount?: string | null;
            /** Source Unit Price */
            source_unit_price?: string | null;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit?: string | null;
        };
        /** OrderLineResponse */
        OrderLineResponse: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /** Delivered Quantity */
            delivered_quantity: string;
            /** Description */
            description: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Item Code */
            item_code?: string | null;
            /** Item Name */
            item_name?: string | null;
            /** Line Number */
            line_number: number;
            material?: components["schemas"]["OrderMaterialSummary"] | null;
            /** Material Id */
            material_id?: string | null;
            /** Quantity */
            quantity: string;
            quantity_policy: components["schemas"]["QuantityPolicy"];
            /** Remaining Quantity */
            remaining_quantity: string;
            /** Source Amount */
            source_amount: string | null;
            /** Source Quantity Text */
            source_quantity_text: string;
            /** Source Unit */
            source_unit: string | null;
            /** Source Unit Price */
            source_unit_price: string | null;
            /** Specification */
            specification?: string | null;
        };
        /** OrderMaterialChoice */
        OrderMaterialChoice: {
            /** Expected Material Version */
            expected_material_version: number;
            /** Line Number */
            line_number: number;
            mapping?: components["schemas"]["MaterialMappingChoice"] | null;
            /**
             * Material Id
             * Format: uuid
             */
            material_id: string;
        };
        /** OrderMaterialLink */
        OrderMaterialLink: {
            /** Customer Code */
            customer_code?: string | null;
            /**
             * Expected Mapping Version
             * @default 0
             */
            expected_mapping_version: number;
            /** Expected Material Version */
            expected_material_version?: number | null;
            /**
             * Line Id
             * Format: uuid
             */
            line_id: string;
            /** Material Id */
            material_id?: string | null;
            new_material?: components["schemas"]["OrderNewMaterial"] | null;
            /**
             * Remember Code
             * @default false
             */
            remember_code: boolean;
        };
        /** OrderMaterialLinksInput */
        OrderMaterialLinksInput: {
            /** Expected Version */
            expected_version: number;
            /** Lines */
            lines: components["schemas"]["OrderMaterialLink"][];
            /** Reason */
            reason?: string | null;
        };
        /** OrderMaterialLinksResult */
        OrderMaterialLinksResult: {
            /** Changes */
            changes: {
                [key: string]: unknown;
            }[];
            /** Material Links */
            material_links?: {
                [key: string]: unknown;
            }[];
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Revision Number */
            revision_number?: number | null;
            /** Sha256 */
            sha256?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "deleted";
            /** Version */
            version: number;
        };
        /** OrderMaterialSuggestion */
        OrderMaterialSuggestion: {
            /** Automatic */
            automatic: boolean;
            /** Line Number */
            line_number: number;
            mapping: components["schemas"]["MaterialMappingChoice"];
            material: components["schemas"]["OrderMaterialSummary"];
        };
        /** OrderMaterialSummary */
        OrderMaterialSummary: {
            /** Active */
            active: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Own Code */
            own_code: string;
            /** Specification */
            specification: string | null;
            /** Unit */
            unit: string | null;
            /** Version */
            version: number;
        };
        /** OrderNewMaterial */
        OrderNewMaterial: {
            /** Name */
            name: string;
            /** Own Code */
            own_code?: string | null;
            /** Specification */
            specification?: string | null;
            /** Unit */
            unit?: string | null;
        };
        /** OrderPreview */
        OrderPreview: {
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Customer Name */
            customer_name: string;
            /** Material Suggestions */
            material_suggestions?: components["schemas"]["OrderMaterialSuggestion"][];
            order: components["schemas"]["EvidenceOrder"];
        };
        /** OrderResult */
        OrderResult: {
            /** Material Links */
            material_links?: {
                [key: string]: unknown;
            }[];
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Revision Number */
            revision_number?: number | null;
            /** Sha256 */
            sha256?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "deleted";
            /** Version */
            version: number;
        };
        /** PreviewDeliveryLayout */
        PreviewDeliveryLayout: {
            config: components["schemas"]["DeliveryLayoutConfig"];
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /**
             * Locale
             * @default zh-CN
             * @enum {string}
             */
            locale: "zh-CN" | "en";
        };
        /** QuantityPolicy */
        QuantityPolicy: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /**
             * Mode
             * @enum {string}
             */
            mode: "INTEGER_ONLY" | "DECIMAL_ALLOWED" | "UNKNOWN";
            /** Version */
            version: string;
            /** Warning Codes */
            warning_codes: string[];
        };
        /** ReleaseInput */
        ReleaseInput: {
            /**
             * Allocation Id
             * Format: uuid
             */
            allocation_id: string;
            /** Allocation Version */
            allocation_version: number;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
        };
        /** ReserveInput */
        ReserveInput: {
            /**
             * Approval Id
             * Format: uuid
             */
            approval_id: string;
            /** Approval Version */
            approval_version: number;
            /** Expected Version */
            expected_version: number;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
        };
        /** ReviewInput */
        ReviewInput: {
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /** Expected Version */
            expected_version: number;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
        };
        /** ReviewPage */
        ReviewPage: {
            /** Items */
            items: components["schemas"]["StatementReview"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** ReviewTransfer */
        ReviewTransfer: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Approval Id */
            approval_id: string | null;
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /**
             * Review Id
             * Format: uuid
             */
            review_id: string;
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "claimed" | "approved" | "released";
            /** Version */
            version: number;
        };
        /** RevisionInput */
        RevisionInput: {
            /** Expected Version */
            expected_version: number;
            order: components["schemas"]["OrderInput"];
            /** Reason */
            reason: string;
        };
        /** RevisionSummary */
        RevisionSummary: {
            /** Confirmed At */
            confirmed_at: string;
            /** Parent Revision Id */
            parent_revision_id: string | null;
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Revision Number */
            revision_number: number;
            /** Sha256 */
            sha256: string;
        };
        /** SaveArchiveSettings */
        SaveArchiveSettings: {
            /** Expected Version */
            expected_version: number;
            /**
             * Rule
             * @enum {string}
             */
            rule: "date" | "customer" | "month_customer";
        };
        /** SaveDeliveryLayout */
        SaveDeliveryLayout: {
            config: components["schemas"]["DeliveryLayoutConfig"];
            /** Expected Version */
            expected_version: number;
        };
        /** SaveDraftInput */
        SaveDraftInput: {
            /** Adjustments */
            adjustments?: components["schemas"]["AdjustmentInput"][];
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Expected Version */
            expected_version: number;
            /** Lines */
            lines?: components["schemas"]["StatementLineInput"][];
            /** Period End */
            period_end: string;
            /** Period Start */
            period_start: string;
            /**
             * Reason
             * @default
             */
            reason: string;
            /**
             * Tax Mode
             * @enum {string}
             */
            tax_mode: "included" | "untaxed_final" | "add_tax";
            /** Tax Rate */
            tax_rate: string;
        };
        /** SentInput */
        SentInput: {
            /** Expected Version */
            expected_version: number;
            /**
             * Export Id
             * Format: uuid
             */
            export_id: string;
            /**
             * Note
             * @default
             */
            note: string;
            /** Occurred On */
            occurred_on: string;
            /** Person */
            person: string;
        };
        /** SessionResponse */
        SessionResponse: {
            /** Csrf Token */
            csrf_token: string;
            user: components["schemas"]["SessionUser"];
        };
        /** SessionUser */
        SessionUser: {
            /** Id */
            id: string;
            /**
             * Role
             * @enum {string}
             */
            role: "admin" | "operator" | "viewer";
            /** Username */
            username: string;
        };
        /** SettleInput */
        SettleInput: {
            /** Expected Version */
            expected_version: number;
            /** Fees Confirmed */
            fees_confirmed: boolean;
            /** Preview Token */
            preview_token: string;
            /** Reason */
            reason: string;
            /**
             * Reconfirmation
             * @enum {string}
             */
            reconfirmation: "unknown" | "not_required" | "received";
        };
        /** SettlementLine */
        SettlementLine: {
            /**
             * Allocation Id
             * Format: uuid
             */
            allocation_id: string;
            /**
             * Allocation Status
             * @enum {string}
             */
            allocation_status: "reserved" | "settled";
            /**
             * Approval Id
             * Format: uuid
             */
            approval_id: string;
            /** Approval Version */
            approval_version: number;
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /**
             * External Document Number
             * @default
             */
            external_document_number: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /**
             * Reason
             * @default
             */
            reason: string;
            source: components["schemas"]["StatementSource"];
            /**
             * Status
             * @enum {string}
             */
            status: "included" | "deferred" | "source_void" | "released";
            /** Unit Price */
            unit_price?: string | null;
        };
        /** SettlementPreviewInput */
        SettlementPreviewInput: {
            /** Expected Version */
            expected_version: number;
            /** Fees Confirmed */
            fees_confirmed: boolean;
            /** Reason */
            reason: string;
            /**
             * Reconfirmation
             * @enum {string}
             */
            reconfirmation: "unknown" | "not_required" | "received";
        };
        /** SourceList */
        SourceList: {
            /** Items */
            items: components["schemas"]["SourceSummary"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** SourceResult */
        SourceResult: {
            /** Original Sha256 */
            original_sha256: string;
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
        };
        /** SourceSummary */
        SourceSummary: {
            /** Created At */
            created_at: string;
            /** Extraction Id */
            extraction_id: string | null;
            /** Filename */
            filename: string;
            /** Media Type */
            media_type: string;
            /** Order Id */
            order_id: string | null;
            /**
             * Source Id
             * Format: uuid
             */
            source_id: string;
        };
        /** StatementAdjustment */
        StatementAdjustment: {
            /** Amount */
            amount: string;
            /** Delivery Id */
            delivery_id?: string | null;
            /** Kind */
            kind: string;
            /** Order Line Id */
            order_line_id?: string | null;
            /** Reason */
            reason: string;
            /**
             * Stage
             * @enum {string}
             */
            stage: "before_tax" | "after_tax";
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "needs_review";
        };
        /** StatementAllocation */
        StatementAllocation: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /**
             * Approval Id
             * Format: uuid
             */
            approval_id: string;
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Settlement Version */
            settlement_version: number | null;
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "reserved" | "settled" | "released" | "superseded";
            /** Superseded Version */
            superseded_version: number | null;
            /** Unit Price */
            unit_price: string;
            /** Version */
            version: number;
        };
        /** StatementApproval */
        StatementApproval: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Available Quantity */
            available_quantity: string;
            correction?: components["schemas"]["StatementCorrection"] | null;
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /**
             * External Document Number
             * @default
             */
            external_document_number: string;
            /**
             * Feedback Id
             * Format: uuid
             */
            feedback_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Reserved Quantity */
            reserved_quantity: string;
            /** Review Quantity */
            review_quantity: string;
            /**
             * Sent Id
             * Format: uuid
             */
            sent_id: string;
            /** Settled Quantity */
            settled_quantity: string;
            source: components["schemas"]["StatementSource"];
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
            /** Target End */
            target_end: string;
            /** Target Start */
            target_start: string;
            /** Unit Price */
            unit_price: string;
            /** Version */
            version: number;
        };
        /** StatementApprovalRef */
        StatementApprovalRef: {
            /**
             * Approval Id
             * Format: uuid
             */
            approval_id: string;
            /**
             * Feedback Id
             * Format: uuid
             */
            feedback_id: string;
            /**
             * Sent Id
             * Format: uuid
             */
            sent_id: string;
            /** Version */
            version: number;
        };
        /** StatementCalculation */
        StatementCalculation: {
            /** Line Amounts */
            line_amounts: (string | null)[];
            /** Priced Subtotal */
            priced_subtotal: string;
            /** Tax Amount */
            tax_amount: string | null;
            /** Tax Base */
            tax_base: string | null;
            /** Total */
            total: string | null;
            /** Warnings */
            warnings: string[];
        };
        /** StatementCandidate */
        StatementCandidate: {
            /** Available Quantity */
            available_quantity: string;
            /** Canonical Unit */
            canonical_unit: string | null;
            /** Cross Period */
            cross_period: boolean;
            /**
             * Currency
             * @constant
             */
            currency: "CNY";
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Delivery Date */
            delivery_date: string;
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /** Description */
            description: string;
            /** Item Code */
            item_code: string | null;
            /** Item Name */
            item_name: string | null;
            /** Line Number */
            line_number: number;
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Order Number */
            order_number?: string | null;
            /** Quantity */
            quantity: string;
            quantity_policy: components["schemas"]["StatementUnitPolicy"];
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Source Amount */
            source_amount: string | null;
            /** Source Unit */
            source_unit: string | null;
            /** Source Unit Price */
            source_unit_price: string | null;
            /** Specification */
            specification: string | null;
        };
        /** StatementCandidatePage */
        StatementCandidatePage: {
            /** Items */
            items: components["schemas"]["StatementCandidate"][];
            /** Next Cursor */
            next_cursor: string | null;
            /** Overlapping Statements */
            overlapping_statements: string[];
        };
        /** StatementCorrection */
        StatementCorrection: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /**
             * Cause
             * @enum {string}
             */
            cause: "entry_error" | "customer_change";
            /**
             * Disposition
             * @enum {string}
             */
            disposition: "review" | "pending";
            /**
             * Evidence Id
             * Format: uuid
             */
            evidence_id: string;
            /** No Downstream Effects */
            no_downstream_effects: boolean;
            /** Previous Quantity */
            previous_quantity: string;
            /** Previous Unit Price */
            previous_unit_price: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Recorded At */
            recorded_at: string;
            /** Unit Price */
            unit_price: string;
        };
        /** StatementDetail */
        StatementDetail: {
            /** Adjustments */
            adjustments: components["schemas"]["StatementAdjustment"][];
            /** Approval Refs */
            approval_refs?: components["schemas"]["StatementApprovalRef"][];
            calculation: components["schemas"]["StatementCalculation"];
            /** Confirmation Evidence Ids */
            confirmation_evidence_ids?: string[];
            correction?: components["schemas"]["StatementCorrection"] | null;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Customer Name */
            customer_name: string;
            /** Fees Confirmed */
            fees_confirmed: boolean;
            /** History */
            history: components["schemas"]["StatementEvent"][];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Lines */
            lines: components["schemas"]["StatementLine"][];
            /** Period End */
            period_end: string;
            /** Period Start */
            period_start: string;
            /**
             * Reconfirmation
             * @enum {string}
             */
            reconfirmation: "unknown" | "not_required" | "received";
            /** Settlement Lines */
            settlement_lines: components["schemas"]["SettlementLine"][];
            /**
             * Status
             * @enum {string}
             */
            status: "draft" | "abandoned" | "void" | "confirmed";
            /**
             * Tax Mode
             * @enum {string}
             */
            tax_mode: "included" | "untaxed_final" | "add_tax";
            /** Tax Rate */
            tax_rate: string;
            /** Version */
            version: number;
        };
        /** StatementEvent */
        StatementEvent: {
            /** Action */
            action: string;
            /** Reason */
            reason: string;
            /** Snapshot */
            snapshot: {
                [key: string]: unknown;
            };
            /** Version */
            version: number;
        };
        /** StatementEvidence */
        StatementEvidence: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Export Id */
            export_id: string | null;
            /** Filename */
            filename: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "sent" | "feedback";
            /** Media Type */
            media_type: string | null;
            /** Note */
            note: string;
            /** Object Hash */
            object_hash: string | null;
            /** Occurred On */
            occurred_on: string;
            /** Person */
            person: string;
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
            /** Statement Version */
            statement_version: number;
        };
        /** StatementExportDetail */
        StatementExportDetail: {
            /** Created At */
            created_at: string;
            /** Current */
            current: boolean;
            /** Customer Template Id */
            customer_template_id?: string | null;
            /** Error Code */
            error_code: string | null;
            /** File Hash */
            file_hash: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Locale
             * @default zh-CN
             * @enum {string}
             */
            locale: "zh-CN" | "en" | "source";
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
            /**
             * Statement Status
             * @default draft
             * @enum {string}
             */
            statement_status: "draft" | "confirmed";
            /** Statement Version */
            statement_version: number;
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "failed" | "ready";
            /** Template Id */
            template_id: string;
            /** Template Name */
            template_name: string;
            /** Template Version */
            template_version: number;
        };
        /** StatementExportInput */
        StatementExportInput: {
            /** Customer Template Id */
            customer_template_id?: string | null;
            /** Expected Version */
            expected_version: number;
            /**
             * Locale
             * @default zh-CN
             * @enum {string}
             */
            locale: "zh-CN" | "en";
            /** Template Id */
            template_id?: ("standard-v1" | "delivery-v1" | "customer-v1") | null;
        };
        /** StatementExportPage */
        StatementExportPage: {
            /** Items */
            items: components["schemas"]["StatementExportDetail"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** StatementLifecycleView */
        StatementLifecycleView: {
            /** Allocations */
            allocations: components["schemas"]["StatementAllocation"][];
            /** Approvals */
            approvals: components["schemas"]["StatementApproval"][];
            /** Evidence */
            evidence: components["schemas"]["StatementEvidence"][];
            /** History */
            history: components["schemas"]["LifecycleHistory"][];
            /** Review Transfers */
            review_transfers: components["schemas"]["ReviewTransfer"][];
            /** Reviews */
            reviews: components["schemas"]["StatementReview"][];
        };
        /** StatementLine */
        StatementLine: {
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /**
             * External Document Number
             * @default
             */
            external_document_number: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /**
             * Reason
             * @default
             */
            reason: string;
            source: components["schemas"]["StatementSource"];
            /**
             * Status
             * @enum {string}
             */
            status: "included" | "deferred" | "source_void" | "released";
            /** Unit Price */
            unit_price?: string | null;
        };
        /** StatementLineInput */
        StatementLineInput: {
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /**
             * External Document Number
             * @default
             */
            external_document_number: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /**
             * Reason
             * @default
             */
            reason: string;
            /** Unit Price */
            unit_price?: string | null;
        };
        /** StatementPage */
        StatementPage: {
            /** Items */
            items: components["schemas"]["StatementDetail"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** StatementReview */
        StatementReview: {
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /**
             * External Document Number
             * @default
             */
            external_document_number: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Quantity */
            quantity: string;
            /** Reason */
            reason: string;
            /** Remaining Quantity */
            remaining_quantity: string;
            source: components["schemas"]["StatementSource"];
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
            /** Version */
            version: number;
        };
        /** StatementSettingsDetail */
        StatementSettingsDetail: {
            /** Customer Template Id */
            customer_template_id?: string | null;
            /** Cycle Day */
            cycle_day: number | null;
            /**
             * Tax Mode
             * @enum {string}
             */
            tax_mode: "included" | "untaxed_final" | "add_tax";
            /** Tax Rate */
            tax_rate: string;
            /**
             * Template Id
             * @enum {string}
             */
            template_id: "standard-v1" | "delivery-v1" | "customer-v1";
            /** Version */
            version: number;
        };
        /** StatementSettingsInput */
        StatementSettingsInput: {
            /** Customer Template Id */
            customer_template_id?: string | null;
            /** Cycle Day */
            cycle_day?: number | null;
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
            /**
             * Tax Mode
             * @enum {string}
             */
            tax_mode: "included" | "untaxed_final" | "add_tax";
            /** Tax Rate */
            tax_rate: string;
            /**
             * Template Id
             * @default standard-v1
             * @enum {string}
             */
            template_id: "standard-v1" | "delivery-v1" | "customer-v1";
        };
        /** StatementSource */
        StatementSource: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /**
             * Currency
             * @constant
             */
            currency: "CNY";
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** Delivery Date */
            delivery_date: string;
            /**
             * Delivery Id
             * Format: uuid
             */
            delivery_id: string;
            /** Description */
            description: string;
            /** Item Code */
            item_code: string | null;
            /** Item Name */
            item_name: string | null;
            /** Line Number */
            line_number: number;
            /**
             * Order Id
             * Format: uuid
             */
            order_id: string;
            /**
             * Order Line Id
             * Format: uuid
             */
            order_line_id: string;
            /** Order Number */
            order_number?: string | null;
            /** Quantity */
            quantity: string;
            quantity_policy: components["schemas"]["StatementUnitPolicy"];
            /**
             * Revision Id
             * Format: uuid
             */
            revision_id: string;
            /** Source Amount */
            source_amount: string | null;
            /** Source Unit */
            source_unit: string | null;
            /** Source Unit Price */
            source_unit_price: string | null;
            /** Specification */
            specification: string | null;
        };
        /** StatementUnitPolicy */
        StatementUnitPolicy: {
            /** Canonical Unit */
            canonical_unit: string | null;
            /**
             * Mode
             * @enum {string}
             */
            mode: "INTEGER_ONLY" | "DECIMAL_ALLOWED" | "UNKNOWN";
            /** Version */
            version: string;
            /** Warning Codes */
            warning_codes: string[];
        };
        /** StatusInput */
        StatusInput: {
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
        };
        /** TemplateDetail */
        TemplateDetail: {
            /** Created At */
            created_at: string;
            /**
             * Customer Id
             * Format: uuid
             */
            customer_id: string;
            /** File Hash */
            file_hash: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            mapping: components["schemas"]["TemplateMapping"];
            /** Name */
            name: string;
            /** Version */
            version: number;
        };
        /** TemplateFileInput */
        TemplateFileInput: {
            /** Content Base64 */
            content_base64: string;
            /** Filename */
            filename: string;
        };
        /** TemplateImportInput */
        TemplateImportInput: {
            /** Content Base64 */
            content_base64: string;
            /** Filename */
            filename: string;
            /** Inspected Sha256 */
            inspected_sha256: string;
            mapping: components["schemas"]["TemplateMapping"];
            /** Name */
            name: string;
        };
        /** TemplateInspection */
        TemplateInspection: {
            /** Columns */
            columns: number;
            /** File Hash */
            file_hash: string;
            /** Grid */
            grid: string[][];
            /** Rows */
            rows: number;
            /** Sheet Name */
            sheet_name: string;
            suggested_mapping: components["schemas"]["TemplateMapping"] | null;
        };
        /** TemplateMapping */
        TemplateMapping: {
            /** Cells */
            cells: {
                [key: string]: string;
            };
            /** Columns */
            columns: {
                [key: string]: string;
            };
            /** Detail End Row */
            detail_end_row: number;
            /** Detail Start Row */
            detail_start_row: number;
            /** Sheet Name */
            sheet_name: string;
        };
        /** TemplatePage */
        TemplatePage: {
            /** Items */
            items: components["schemas"]["TemplateDetail"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** TemplatePreview */
        TemplatePreview: {
            /** Content Base64 */
            content_base64: string;
            /** Grid */
            grid: string[][];
            /** Statement Version */
            statement_version: number;
        };
        /** TemplatePreviewInput */
        TemplatePreviewInput: {
            /** Content Base64 */
            content_base64: string;
            /** Expected Version */
            expected_version: number;
            /** Filename */
            filename: string;
            /** Inspected Sha256 */
            inspected_sha256: string;
            mapping: components["schemas"]["TemplateMapping"];
            /**
             * Statement Id
             * Format: uuid
             */
            statement_id: string;
        };
        /** VoidDeliveryInput */
        VoidDeliveryInput: {
            /** Expected Version */
            expected_version: number;
            /** Reason */
            reason: string;
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
    getArchiveSettings: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["ArchiveSettings"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveArchiveSettings: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveArchiveSettings"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ArchiveSettings"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listArchiveSources: {
        parameters: {
            query: {
                kind: "source" | "delivery" | "statement_export";
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["ArchiveSources"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listArchives: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["ArchiveBatches"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createArchive: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchiveCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ArchiveBatch"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewArchive: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivePreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ArchivePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getArchive: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                identifier: string;
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
                    "application/json": components["schemas"]["ArchiveBatch"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    downloadArchive: {
        parameters: {
            query?: {
                historical?: boolean;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                identifier: string;
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
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    generateArchive: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                identifier: string;
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
                    "application/json": components["schemas"]["ArchiveBatch"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    login: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    logout: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
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
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSession: {
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
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listCustomers: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["CustomerResponse"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createCustomer: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CustomerInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CustomerResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStatementSettings: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
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
                    "application/json": components["schemas"]["StatementSettingsDetail"] | null;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveStatementSettings: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatementSettingsInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementSettingsDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listStatementTemplates: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
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
                    "application/json": components["schemas"]["TemplatePage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    importStatementTemplate: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateImportInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    inspectStatementTemplate: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateFileInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplateInspection"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewStatementTemplate: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplatePreviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TemplatePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStatementTemplate: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                customer_id: string;
                template_id: string;
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
                    "application/json": components["schemas"]["TemplateDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listDeliveries: {
        parameters: {
            query?: {
                customer_id?: string | null;
                cursor?: string | null;
                limit?: number;
                order_id?: string | null;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["DeliveryPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createDelivery: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeliveryInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliveryDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getDelivery: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                delivery_id: string;
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
                    "application/json": components["schemas"]["DeliveryDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    printDelivery: {
        parameters: {
            query?: {
                locale?: "zh-CN" | "en";
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                delivery_id: string;
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
                    "text/html": string;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    voidDelivery: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                delivery_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoidDeliveryInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliveryDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getDeliveryLayout: {
        parameters: {
            query?: {
                locale?: "zh-CN" | "en";
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["DeliveryLayoutDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveDeliveryLayout: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveDeliveryLayout"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliveryLayoutDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewDeliveryLayout: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreviewDeliveryLayout"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getEvidence: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                revision_id: string;
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
                    "application/json": components["schemas"]["EvidenceResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    downloadEvidence: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                revision_id: string;
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
                    "application/json": unknown;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getExtraction: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                extraction_id: string;
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
                    "application/json": components["schemas"]["ExtractionDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getSourcePage: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                extraction_id: string;
                number: number;
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
                    "application/json": unknown;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getLiveness: {
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
                    "application/json": components["schemas"]["Liveness"];
                };
            };
        };
    };
    getReadiness: {
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
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listMaterialCodes: {
        parameters: {
            query?: {
                material_id?: string | null;
                customer_id?: string | null;
                customer_code?: string | null;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["MaterialCodeList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveMaterialCode: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialCodeInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialCodeResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listMaterials: {
        parameters: {
            query?: {
                q?: string;
                offset?: number;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["MaterialList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createMaterial: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    confirmMaterialImport: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialImportConfirm"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialImportResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    inspectMaterialImport: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialImportFile"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialImportInspection"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewMaterialImport: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialImportInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialImportPreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    updateMaterial: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                material_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaterialUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaterialResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    confirmOrder: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrderInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listOpenLines: {
        parameters: {
            query?: {
                customer_id?: string | null;
                cursor?: string | null;
                limit?: number;
                status?: "active" | "deleted";
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["OpenLinesResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewOrder: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrderInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderPreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getOrder: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                order_id: string;
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
                    "application/json": components["schemas"]["OrderDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    deleteOrder: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    linkOrderMaterials: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OrderMaterialLinksInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderMaterialLinksResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    restoreOrder: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reviseOrder: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                order_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrderResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listSources: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["SourceList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    uploadSource: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-Filename": string;
                "content-type": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/pdf": string;
                "image/jpeg": string;
                "image/png": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    downloadSource: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                source_id: string;
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
                    "application/json": unknown;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    extractSource: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                source_id: string;
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
                    "application/json": components["schemas"]["ExtractionResult"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listStatementApprovals: {
        parameters: {
            query: {
                customer_id: string;
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["ApprovalPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    correctStatementApproval: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorrectApprovalInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementApproval"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewApprovalCorrection: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorrectApprovalPreviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LifecyclePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    deferStatementApproval: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeferInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementApproval"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewStatementDefer: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeferPreviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LifecyclePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStatementCandidates: {
        parameters: {
            query: {
                customer_id: string;
                period_start: string;
                period_end: string;
                statement_id?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["StatementCandidatePage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    downloadStatementEvidence: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                evidence_id: string;
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
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    downloadStatementExport: {
        parameters: {
            query?: {
                historical?: boolean;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                export_id: string;
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
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": string;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    generateStatementExport: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                export_id: string;
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
                    "application/json": components["schemas"]["StatementExportDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listStatementReviews: {
        parameters: {
            query: {
                customer_id: string;
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["ReviewPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listStatementDrafts: {
        parameters: {
            query: {
                customer_id: string;
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
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
                    "application/json": components["schemas"]["StatementPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createStatementDraft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DraftInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStatementDraft: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
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
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    abandonStatementDraft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AbandonDraftInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    approveStatementQuantity: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApproveInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementApproval"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    claimStatementReview: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClaimReviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    correctStatementSettlement: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorrectSettlementInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewSettlementCorrection: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorrectSettlementPreviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LifecyclePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    listStatementExports: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number;
            };
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
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
                    "application/json": components["schemas"]["StatementExportPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createStatementExport: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatementExportInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementExportDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    recordStatementFeedback: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementEvidence"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getStatementLifecycle: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
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
                    "application/json": components["schemas"]["StatementLifecycleView"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    releaseStatementAllocation: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReleaseInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementAllocation"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reopenStatementDraft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveDraftInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reserveStatementApproval: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReserveInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementAllocation"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reviewStatementQuantity: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementReview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveStatementDraft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveDraftInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    recordStatementSent: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SentInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementEvidence"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    settleStatement: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettleInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    previewStatementSettlement: {
        parameters: {
            query?: never;
            header?: {
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettlementPreviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LifecyclePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    voidStatementDraft: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "X-CSRF-Token"?: string | null;
            };
            path: {
                statement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AbandonDraftInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatementDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
