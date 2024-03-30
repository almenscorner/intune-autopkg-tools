import os
import requests
import json

TEAMS_WEBHOOK = os.getenv("TEAMS_WEBHOOK")

def _send_teams_alert(title, message, error=False, imported=False, id=None):

    data = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.6",
                    "msteams": {
                        "width": "Full"
                    },
                    "body": [
                        {
                            "type": "Container",
                            "style": "attention" if error else "good",
                            "bleed": True,
                            "size": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": ""
                                }
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": "📦 AutoPkg",
                            "wrap": True,
                            "size": "large",
                        },
                        {
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "type": "Column",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": title,
                                            "wrap": True,
                                            "isSubtle": True,
                                        },
                                        {
                                            "type": "TextBlock",
                                            "text": message,
                                            "wrap": True,
                                        },
                                    ],
                                }
                            ],
                        },
                    ],
                },
            }
        ],
    }

    if imported:
        data["attachments"][0]["content"]["actions"] = [
            {
                "type": "Action.OpenUrl",
                "title": "View App in Intune",
                "url": f"https://intune.microsoft.com/#view/Microsoft_Intune_Apps/SettingsMenu/~/0/appId/{id}"
            }
        ]
    
    data = json.dumps(data)
    
    response = requests.post(url=TEAMS_WEBHOOK, data=data)

    if response.status_code != 200:
        raise ValueError(
            f"Request to Teams returned an error {response.status_code}, the response is:\n{response.text}"
        )


def _error_alerts(recipe):
    if not recipe.verified:
        if recipe.name:
            task_title = f"❌ {recipe.name} failed trust verification"
        else:
            task_title = "❌ Recipe failed trust verification"
        task_description = "Update trust verification manually"
        _send_teams_alert(task_title, task_description, error=True)
    elif recipe.error:
        task_title = f"❌ {recipe.name} failed"
        if not recipe.results["failed"]:
            task_description = "Unknown error"
        else:
            task_description = recipe.results["failed"][0]["message"]
        _send_teams_alert(task_title, task_description, error=True)


def _updated_alerts(recipe):
    if recipe.updated:
        task_title = f"✅ Imported {recipe.name} {str(recipe.updated_version)}"
        result_id = recipe.results["imported"][0]["intune_app_id"]
        task_description = (
            f'**Name:** {recipe.results['imported'][0]['name']}'
            + "\r \r"
            + f'**Intune App ID:** {result_id}'
            + "\r \r"
            + f'**Content Version ID:** {recipe.results['imported'][0]['content_version_id']}'
            + "\r \r"
        )
        _send_teams_alert(task_title, task_description, imported=True, id=result_id)


def _removed_alerts(recipe, opts):
    if opts.cleanup_list and recipe.removed:
        task_title = f"🗑 Removed old versions of {recipe.name}"
        task_description = ""
        task_description += (
            f'**Remove Count:** {recipe.results["removed"][0]["removed count"]}'
            + "\r \r"
            + f'**Removed Versions:** {recipe.results["removed"][0]["removed versions"]}'
            + "\r \r"
            + f'**Keep Count:** {recipe.results["removed"][0]["keep count"]}'
        )
        _send_teams_alert(task_title, task_description)


def _promoted_alerts(recipe, opts):
    if opts.promote_list and recipe.promoted:
        task_title = "🚀 Promoted %s" % recipe.name
        task_description = ""
        task_description += (
            f'**Promotions:** {recipe.results["promoted"][0]["promotions"]}'
            + "\r \r"
            + f'**Blacklisted Versions:** {recipe.results["promoted"][0]["blacklisted versions"]}'
        )
        _send_teams_alert(task_title, task_description)


def notify_teams(recipe, opts):
    _error_alerts(recipe)
    _updated_alerts(recipe)
    _removed_alerts(recipe, opts)
    _promoted_alerts(recipe, opts)
