"""
Slack action handlers for morning summary interactive buttons.
"""

import re
from slack_bolt import App


def register_morning_summary_handlers(app: App):
    """
    Register all interactive handlers for morning summary Block Kit buttons.

    Args:
        app: Slack Bolt app instance
    """

    @app.action("view_full_analysis")
    def handle_view_full_analysis(ack, body, client):
        """Handle 'View Full Analysis' button click."""
        ack()

        # Send detailed analysis in thread
        thread_ts = body['message']['ts']
        channel = body['channel']['id']

        # Get detailed data
        from morning_summary import get_country_acquisitions_with_comparisons, get_crm_yesterday

        country_result = get_country_acquisitions_with_comparisons()
        country_data = country_result['aggregated']
        crm_data = get_crm_yesterday()

        # Build detailed message
        details = []
        details.append("*📊 Detailed Analysis*\n")

        # Detailed breakdown by country
        for country in country_data:
            from morning_summary import get_country_flag
            flag = get_country_flag(country['country'])

            details.append(f"\n*{flag} {country['country']}*")
            details.append(f"• Total: {country['nb_acquis']:,} acquisitions")
            details.append(f"• YoY (N-1): {country['nb_acquis_n1']:,} ({country['var_n1_pct']:+.1f}%)")
            details.append(f"• MoM (M-1): {country['nb_acquis_m1']:,}")
            details.append(f"• Committed: {country['pct_committed']:.1f}%")
            details.append(f"• NEW NEW: {country['pct_new_new']:.1f}%")
            details.append(f"• Top coupon: {country['top_coupon']}")
            details.append(f"• Cycle cumul: {country['cycle_cumul_ty']:,} (YoY: {country['cycle_var_pct']:+.1f}%)")

        # CRM section
        if crm_data:
            details.append(f"\n*✉️ CRM Campaigns ({len(crm_data)} sent)*")
            for campaign in crm_data[:10]:
                camp_name = str(campaign.get('name', 'N/A'))[:40]
                sent = int(campaign.get('delivered', campaign.get('targeted', 0)))
                opened = int(campaign.get('open_uniques', 0))
                clicked = int(campaign.get('click_uniques', 0))
                open_rate = (opened / sent * 100) if sent > 0 else 0
                click_rate = (clicked / sent * 100) if sent > 0 else 0

                details.append(f"• {camp_name}: {sent:,} sent, {open_rate:.1f}% open, {click_rate:.1f}% click")

        # Send as thread
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="\n".join(details)
        )

    # Note: Use regex pattern to match all country detail buttons
    @app.action(re.compile(r"^view_country_details_.*"))
    def handle_country_details(ack, body, action, client):
        """Handle individual country 'Details' button click."""
        ack()

        # Extract country code from action_id
        action_id = action['action_id']
        country_code = action_id.replace('view_country_details_', '')

        # Send ephemeral message with country details
        user_id = body['user']['id']
        channel = body['channel']['id']

        # Get country data
        from morning_summary import get_country_acquisitions_with_comparisons, get_country_flag

        country_result = get_country_acquisitions_with_comparisons()
        country_data = country_result['aggregated']

        # Find the country
        country_info = None
        for c in country_data:
            if c['country'] == country_code:
                country_info = c
                break

        if not country_info:
            client.chat_postEphemeral(
                channel=channel,
                user=user_id,
                text=f"⚠️ No data found for {country_code}"
            )
            return

        flag = get_country_flag(country_code)

        # Build detailed country message
        details = []
        details.append(f"*{flag} {country_code} - Detailed Metrics*\n")

        details.append("*Yesterday's Performance*")
        details.append(f"• Total acquisitions: {country_info['nb_acquis']:,}")
        details.append(f"• YoY change: {country_info['var_n1_pct']:+.1f}% (vs {country_info['nb_acquis_n1']:,})")
        details.append(f"• MoM: {country_info['nb_acquis_m1']:,} acquisitions")
        details.append(f"• Committed: {country_info['pct_committed']:.1f}%")
        details.append(f"• NEW NEW: {country_info['pct_new_new']:.1f}%")
        details.append(f"• Top coupon: {country_info['top_coupon']}")

        details.append("\n*Cycle Performance*")
        details.append(f"• Cycle cumul: {country_info['cycle_cumul_ty']:,} (vs {country_info['cycle_cumul_ly']:,} YoY)")
        details.append(f"• Cycle change: {country_info['cycle_var_pct']:+.1f}%")
        details.append(f"• Cycle committed: {country_info['pct_cycle_committed_ty']:.1f}%")
        details.append(f"• Cycle NEW NEW: {country_info['pct_cycle_new_new_ty']:.1f}%")
        details.append(f"• Cycle REACTIVATION: {country_info['pct_cycle_reactivation_ty']:.1f}%")

        client.chat_postEphemeral(
            channel=channel,
            user=user_id,
            text="\n".join(details)
        )

    print("[Morning Summary Handlers] All interactive handlers registered")
