# Intune AutoPkg tools

This repository contains a script that is a wrapper around AutoPkg to automate the process of creating, updating, promoting and deleting macOS apps in Intune using the Intune Uploader processor.

For help getting started with Intune Uploader, see [this wiki](https://github.com/almenscorner/intune-uploader/wiki).

## How it works
This repository contains example overrides for Firefox and UTM, but you can easily add more by creating a new override file in the `overrides` directory.
- `overrides/FirefoxSigned.intune.recipe` - Example override for Firefox, configured with promotion information.
- `overrides/UTM.intune.recipe` - Example override for UTM

The script `autopkg_tools/autopkg_tools.py` will run AutoPkg with specified recipes and then upload or update the resulting app to Intune. The script will also handle the promotion to groups and removal of old versions in Intune.

- `autopkg_tools/recipe_list.json` - List of recipes to run
- `autopkg_tools/promote_list.json` - List of recipes to promote to groups in stages, see [here](https://github.com/almenscorner/intune-uploader/wiki/IntuneAppPromoter) for more information on how to configure this.
- `autopkg_tools/cleanup_list.json` - List of recipes to delete old versions in Intune, when adding a new version, configure the `keep` value to the number of versions to keep. If not configured, the default is 3.

This is run using the workflow `.github/workflows/autopkg.yml` if using GitHub Actions or `autopkg-azure.yml` if using Azure Pipelines.

## GitHub Actions
To use this with GitHub Actions, create a new repository, clone this repository and copy the contents to your repository and add the following secrets to your repository:
- `CLIENT_SECRET` - The client secret of your Intune app registration
- `TEAMS_WEBHOOK` - The webhook URL of the Teams channel you want to post to

Then update the following variables in `.github/workflows/autopkg.yml`:
- `TENANT_ID` - The tenant ID of your Azure AD
- `CLIENT_ID` - The client ID of your Intune app registration

## Azure Pipelines
To use this with Azure Pipelines, create a new project in Azure DevOps, clone this repository and copy the contents to your repository, create a new pipeline using `autopkg-azure.yml` and add the following secret variables to your pipeline:
- `CLIENT_SECRET` - The client secret of your Intune app registration
- `TEAMS_WEBHOOK` - The webhook URL of the Teams channel you want to post to

Then update the following variables in the pipeline:
- `TENANT_ID` - The tenant ID of your Azure AD
- `CLIENT_ID` - The client ID of your Intune app registration

## Credits
[autopkg_tools.py](https://github.com/facebook/IT-CPE/tree/master/legacy/autopkg_tools) from Facebook under a BSD 3-clause license with modifications from [tig](https://6fx.eu) and [Gusto](https://github.com/Gusto/it-cpe-opensource/blob/ac845ca9a4d6eccb8ffb2c05c9c5f31eeed095d5/autopkg/autopkg_tools.py).
