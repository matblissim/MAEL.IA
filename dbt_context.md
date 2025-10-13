# Documentation DBT pour MAEL.IA

*Généré automatiquement depuis le manifest DBT*

**Schémas inclus :** sales, user, inter

---

# Documentation DBT - Modèles de Données
Cette documentation est générée automatiquement depuis DBT.

## Schéma `inter` (109 modèles)
### `inter.adyen_notifications`


---

### `inter.allocation_history`


---

### `inter.archives_products_stock_log`


---

### `inter.b2c_exported_orders`


---

### `inter.b2c_order_notifications`


---

### `inter.boxes`


---

### `inter.boxes_by_day`


---

### `inter.brands`


---

### `inter.brands_correspondances`


---

### `inter.byob_product_link`


---

### `inter.cc_orders_status`


---

### `inter.choose_choices`


---

### `inter.choose_forms`


---

### `inter.choose_users`


---

### `inter.christmas_offer`


---

### `inter.comments`


---

### `inter.company`


---

### `inter.consent`


---

### `inter.consent_topic`


---

### `inter.coupons`


---

### `inter.da_box_acquisition_detail`


---

### `inter.da_box_shipped_detail`


---

### `inter.da_eu_countries`


---

### `inter.da_monthly_sub_baseline`


---

### `inter.expected_inbound_details`


---

### `inter.expected_inbounds`


---

### `inter.ga_transactions`


---

### `inter.gift_cards`


---

### `inter.gift_codes_generated`


---

### `inter.inventory_items`


---

### `inter.invoice_credit_notes`


---

### `inter.invoice_details`


---

### `inter.invoices`


---

### `inter.kit_links`


---

### `inter.lte_kits`


---

### `inter.mini_byob_reexp`


---

### `inter.mini_lte_reexp`


---

### `inter.mini_reexp`


---

### `inter.open_comment_posts`


---

### `inter.optin`


---

### `inter.options`


---

### `inter.order_detail_sub`


---

### `inter.order_detail_sub_options`


---

### `inter.order_details`


---

### `inter.order_status`


---

### `inter.orders`


---

### `inter.orders_status`


---

### `inter.partial_box_paid`
Table des ventes partielles de box

---

### `inter.partial_cancelations`


---

### `inter.payment_profiles`


---

### `inter.payments`


---

### `inter.postmeta`


---

### `inter.posts`


---

### `inter.prepacked_products`


---

### `inter.product_codification`


---

### `inter.product_warehouse_location`


---

### `inter.products`


---

### `inter.products_bundle_component`


---

### `inter.products_detailed_rating`


---

### `inter.products_stock_log`


---

### `inter.purchase_order_items`


---

### `inter.purchase_orders`


---

### `inter.raf`


---

### `inter.raf_offer_details`


---

### `inter.raf_offers`


---

### `inter.raf_order_link`


---

### `inter.raf_reward_moment`


---

### `inter.raf_reward_type`


---

### `inter.raf_sub_link`


---

### `inter.range_of_age`


---

### `inter.reception_details`


---

### `inter.reward_points_history`


---

### `inter.reward_points_history_uses`


---

### `inter.sample_product_link`


---

### `inter.saved_cart`


---

### `inter.saved_cart_details`


---

### `inter.shipping_modes`


---

### `inter.shipup_tracking`


---

### `inter.store_mouvements`


---

### `inter.store_products`


---

### `inter.sub_history`


---

### `inter.sub_offers`


---

### `inter.sub_order_link`


---

### `inter.sub_payments_status`


---

### `inter.sub_suspend_survey_question`


---

### `inter.sub_suspend_survey_question_answer`


---

### `inter.sub_suspend_survey_result`


---

### `inter.sub_suspend_survey_result_answer`


---

### `inter.sub_suspended_reasons`


---

### `inter.survey_answer_meanings`


---

### `inter.survey_answers`


---

### `inter.survey_question_categories`


---

### `inter.survey_questions`


---

### `inter.survey_result_answers`


---

### `inter.survey_results`


---

### `inter.survey_surveys`


---

### `inter.tags`


---

### `inter.term_relationships`


---

### `inter.term_taxonomy`


---

### `inter.terms`


---

### `inter.trackings`


---

### `inter.tva_product`


---

### `inter.user_campaign`


---

### `inter.user_consent`


---

### `inter.user_consent_history`


---

### `inter.user_mailing_list`


---

### `inter.users`


---

### `inter.warehouse`


---

### `inter.yearly_check`


---

## Schéma `sales` (15 modèles)
### `sales.box_acquisition_daily`


---

### `sales.box_acquisition_detail`


---

### `sales.box_committed_not_paid`


---

### `sales.box_gift`


---

### `sales.box_mono`


---

### `sales.box_paused`


---

### `sales.box_refunds`


---

### `sales.box_sales`
Table des ventes de box

**Colonnes :**
| Colonne | Type | Description |
|---------|------|-------------|
| `date` | None | date de la box |
| `dw_country_code` | None | Code pays (FR, DE, etc.) |
| `sub_id` | None | Identifiant unique de l'abonnement |

---

### `sales.box_sales_by_user_by_type`


---

### `sales.kpi_box`


---

### `sales.obj_by_country`


---

### `sales.shop_orders_margin`


---

### `sales.shop_refunds`


---

### `sales.shop_sales`
Table des ventes shop

**Colonnes :**
| Colonne | Type | Description |
|---------|------|-------------|
| `dw_country_code` | None | Code pays pour les ventes shop |

---

### `sales.shop_sales_with_gross_profit`


---

## Schéma `user` (19 modèles)
### `user.Choose_by_user`


---

### `user.crm_data`


---

### `user.customers`


---

### `user.customers_beauty_profile`


---

### `user.customers_carts`


---

### `user.customers_info_perso`


---

### `user.customers_streaming`


---

### `user.splio_data_dedup`


---

### `user.today_inactive`


---

### `user.today_lost`


---

### `user.today_middle`


---

### `user.today_new`


---

### `user.today_prospects`


---

### `user.today_risky`


---

### `user.today_segments`


---

### `user.today_spectators`


---

### `user.today_stars`


---

### `user.today_whales`


---

### `user.user_consent_details`


---

