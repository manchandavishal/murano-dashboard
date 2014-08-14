#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time

from selenium.webdriver.common import by

from muranodashboard.tests.functional import base
from muranodashboard.tests.functional import consts as c
from muranodashboard.tests.functional import utils


class TestSuiteSmoke(base.UITestCase):
    """This class keeps smoke tests which check operability of all main panels
    """
    @utils.ordered
    def test_smoke_environments_panel(self):
        self.go_to_submenu('Environments')
        self.check_panel_is_present('Environments')

    @utils.ordered
    def test_smoke_applications_panel(self):
        self.go_to_submenu('Applications')
        self.check_panel_is_present('Applications')

    @utils.ordered
    def test_smoke_statistics_panel(self):
        self.go_to_submenu('Statistics')
        self.check_panel_is_present('Murano Status')

    @utils.ordered
    def test_smoke_images_panel(self):
        self.navigate_to('Manage')
        self.go_to_submenu('Images')
        self.check_panel_is_present('Marked Images')

    @utils.ordered
    def test_smoke_package_definitions_panel(self):
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')
        self.check_panel_is_present('Package Definitions')


class TestSuiteEnvironment(base.EnvironmentTestCase):
    @utils.ordered
    def test_create_delete_environment(self):
        """Test check ability to create and delete environment

        Scenario:
            1. Create environment
            2. Navigate to this environment
            3. Go back to environment list and delete created environment
        """
        self.go_to_submenu('Environments')
        self.create_environment('test_create_del_env')
        self.go_to_submenu('Environments')
        self.delete_environment('test_create_del_env')
        self.check_element_not_on_page(by.By.LINK_TEXT, 'test_create_del_env')

    @utils.ordered
    def test_edit_environment(self):
        """Test check ability to change environment name

        Scenario:
            1. Create environment
            2. Change environment's name
            3. Check that renamed environment is in environment list
        """
        self.go_to_submenu('Environments')
        self.create_environment('test_edit_env')
        self.go_to_submenu('Environments')
        self.driver.find_element_by_link_text('test_edit_env')

        self.edit_environment(old_name='test_edit_env', new_name='edited_env')
        self.check_element_on_page(by.By.LINK_TEXT, 'edited_env')
        self.check_element_not_on_page(by.By.LINK_TEXT, 'test_edit_env')


class TestSuiteImage(base.ImageTestCase):
    @utils.ordered
    def test_rename_image(self):
        """Test check ability to mark murano image

        Scenario:
            1. Navigate to Images page
            2. Click on button "Mark Image"
            3. Fill the form and submit it
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Images')
        self.driver.find_element_by_id(
            'marked_images__action_mark_image').click()

        self.select_from_list('image', self.image.id)
        new_title = 'RenamedImage ' + str(time.time())
        self.fill_field(by.By.ID, 'id_title', new_title)
        self.select_from_list('type', 'linux')
        self.select_and_click_element('Mark')
        self.check_element_on_page(by.By.XPATH, c.TestImage.format(new_title))

        self.repair_image()

    @utils.ordered
    def test_check_image_info(self):
        """Test check ability to view image details

        Scenario:
            1. Navigate to Images page
            2. Click on the name of selected image, check image info
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Images')
        self.driver.find_element_by_xpath(
            c.TestImage.format(self.image_title) + '//a').click()
        self.assertIn(self.image_title,
                      self.driver.find_element(by.By.XPATH, c.ImageMeta).text)

    @utils.ordered
    def test_delete_image(self):
        """Test check ability to delete image

        Scenario:
            1. Navigate to Images page
            2. Select created image and click on "Delete Metadata"
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Images')
        self.driver.find_element_by_xpath(
            c.DeleteImageMeta.format(self.image_title)).click()
        self.driver.find_element_by_xpath(c.ConfirmDeletion).click()
        self.check_element_not_on_page(by.By,
                                       c.TestImage.format(self.image_title))

        self.repair_image()


class TestSuiteFields(base.FieldsTestCase):
    @utils.ordered
    def test_check_domain_name_field_validation(self):
        """Test checks that validation of domain name field work
        and appropriate error message is appeared after entering
        incorrect domain name

        Scenario:
            1. Navigate to Environments page
            2. Create environment and start to create MockApp service
            3. Set "a" as a domain name and verify error message
            4. Set "aa" as a domain name and check that error message
            didn't appear
            5. Set "@ct!v3" as a domain name and verify error message
            6. Set "active.com" as a domain name and check that error message
            didn't appear
            7. Set "domain" as a domain name and verify error message
            8. Set "domain.com" as a domain name and check that error message
            didn't appear
            9. Set "morethan15symbols.beforedot" as a domain name and
            verify error message
            10. Set "lessthan15.beforedot" as a domain name and check that
            error message didn't appear
            11. Set ".domain.local" as a domain name and
            verify error message
            12. Set "domain.local" as a domain name and check that
            error message didn't appear
        """
        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)
        field_id = self.mockapp_id + "_0-domain"

        self.fill_field(by.By.ID, field_id, value='a')
        self.check_error_message_is_present(
            'Ensure this value has at least 2 characters (it has 1).')
        self.fill_field(by.By.ID, field_id, value='aa')
        self.check_error_message_is_absent(
            'Ensure this value has at least 2 characters (it has 1).')

        self.fill_field(by.By.ID, field_id, value='@ct!v3')
        self.check_error_message_is_present(
            'Only letters, numbers and dashes in the middle are allowed.')

        self.fill_field(by.By.ID, field_id, value='active.com')
        self.check_error_message_is_absent(
            'Only letters, numbers and dashes in the middle are allowed.')

        self.fill_field(by.By.ID, field_id, value='domain')
        self.check_error_message_is_present(
            'Single-level domain is not appropriate.')

        self.fill_field(by.By.ID, field_id, value='domain.com')
        self.check_error_message_is_absent(
            'Single-level domain is not appropriate.')

        self.fill_field(by.By.ID, field_id,
                        value='morethan15symbols.beforedot')
        self.check_error_message_is_present(
            'NetBIOS name cannot be shorter than'
            ' 1 symbol and longer than 15 symbols.')
        self.fill_field(by.By.ID, field_id, value='lessthan15.beforedot')
        self.check_error_message_is_absent(
            'NetBIOS name cannot be shorter than'
            ' 1 symbol and longer than 15 symbols.')

        self.fill_field(by.By.ID, field_id, value='.domain.local')
        self.check_error_message_is_present(
            'Period characters are allowed only when '
            'they are used to delimit the components of domain style names')

        self.fill_field(by.By.ID, field_id, value='domain.local')
        self.check_error_message_is_absent(
            'Period characters are allowed only when '
            'they are used to delimit the components of domain style names')

    @utils.ordered
    def test_check_app_name_validation(self):
        """Test checks validation of field that usually define
        application name

        Scenario:
            1. Navigate to Application Catalog > Applications
            2. Start to create Mock App
            3. Check a set of names, if current name isn't valid
            appropriate error message should appears
        """
        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)

        self.fill_field(by.By.NAME, '0-name', value='a')
        self.check_error_message_is_present(
            'Ensure this value has at least 2 characters (it has 1).')

        self.fill_field(by.By.NAME, '0-name', value='@pp')
        self.check_error_message_is_present(
            'Just letters, numbers, underscores and hyphens are allowed.')

        self.fill_field(by.By.NAME, '0-name', value='AppL1')
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()
        self.wait_element_is_clickable(by.By.LINK_TEXT, '+')

    @utils.ordered
    def test_check_required_field(self):
        """Test checks that fields with parameter 'required=True' in yaml form
        are truly required and can't be omitted

        Scenario:
            1. Navigate to Application Catalog > Applications
            2. Start to create MockApp
            3. Don't type app name in the 'Application Name'
            field that is required and click 'Next',check that there is
            error message
            4. Set app name and click 'Next',
            check that there is no error message
        """
        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)

        self.driver.find_element_by_xpath(c.ButtonSubmit).click()
        self.check_error_message_is_present('This field is required.')

        self.fill_field(by.By.NAME, "0-name", "name")
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()

        self.wait_element_is_clickable(by.By.LINK_TEXT, '+')

    @utils.ordered
    def test_password_validation(self):
        """Test checks password validation

        Scenario:
            1. Navigate to Application Catalog > Applications
            2. Start to create MockApp
            3. Set weak password consisting of numbers,
            check that error message appears
            4. Set different passwords to Password field and Confirm password
            field, check that validation failed
            5. Set correct password. Validation has to pass
        """
        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)

        self.fill_field(by.By.NAME, "0-name", "name")
        self.fill_field(by.By.NAME, '0-adminPassword', value='123456')
        self.check_error_message_is_present(
            'The password must contain at least one letter')
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()
        self.fill_field(by.By.NAME, "0-adminPassword-clone", value='P@ssw0rd')
        self.check_error_message_is_absent('Passwords do not match')
        self.fill_field(by.By.NAME, '0-adminPassword', value='P@ssw0rd')
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()
        self.wait_element_is_clickable(by.By.LINK_TEXT, '+')


class TestSuiteApplications(base.ApplicationTestCase):
    @utils.ordered
    def test_check_transitions_from_one_wizard_to_another(self):
        """Test checks that transitions "Next" and "Back" are not broken

        Scenario:
            1. Navigate to Application Catalog > Applications
            2. Start to create MockApp
            3. Set app name and click on "Next", check that second wizard step
            will appear
            4. Click 'Back' and check that first wizard step is shown
        """
        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)

        self.fill_field(by.By.NAME, "0-name", "name")
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()

        self.driver.find_element_by_id(
            'wizard_{0}_btn'.format(self.mockapp_id)).click()

        self.check_element_on_page(by.By.NAME, "0-name")

    @utils.ordered
    def test_check_ability_create_two_dependent_apps(self):
        """Test checks that using one creation form it is possible to
        add to related apps in the one environment

        Scenario:
            1. Navigate to Application Catalog > Applications
            2. Start to create MockApp
            3. Set app name and click on "Next"
            4. Click '+' and verify that creation of second app is possible
        """

        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)

        self.fill_field(by.By.NAME, "0-name", "app1")
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()

        self.driver.find_element_by_link_text('+').click()
        self.fill_field(by.By.NAME, "0-name", "app2")

    @utils.ordered
    def test_creation_deletion_app(self):
        """Test check ability to create and delete test app

        Scenario:
            1. Navigate to 'Application Catalog'
            2. Click on 'Quick Deploy' for MockApp application
            3. Create TestApp app by filling the creation form
            4. Delete TestApp app from environment
        """

        self.go_to_submenu('Applications')

        self.select_and_click_action_for_app('quick-add', self.mockapp_id)

        self.fill_field(by.By.NAME, '0-name'.format(self.mockapp_id), 'TestA')
        self.driver.find_element_by_xpath(c.ButtonSubmit).click()

        self.driver.find_element_by_xpath(c.InputSubmit).click()

        self.select_from_list('osImage', self.image.name)
        self.driver.find_element_by_xpath(c.InputSubmit).click()
        self.wait_element_is_clickable(by.By.LINK_TEXT, 'Add Component')
        self.check_element_on_page(by.By.LINK_TEXT, 'TestA')
        self.delete_component('TestA')
        self.check_element_not_on_page(by.By.LINK_TEXT, 'TestA')

    @utils.ordered
    def test_modify_package_name(self):
        """Test check ability to change name of the package

        Scenario:
            1. Navigate to 'Package Definitions' page
            2. Select package and click on 'Modify Package'
            3. Rename package
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')
        self.select_action_for_package('PostgreSQL',
                                       'modify_package')
        self.fill_field(by.By.ID, 'id_name', 'PostgreSQL-modified')
        self.driver.find_element_by_xpath(c.InputSubmit).click()

        self.check_element_on_page(by.By.XPATH,
                                   c.AppPackageDefinitions.format(
                                       'PostgreSQL-modified'))

        self.select_action_for_package('PostgreSQL-modified',
                                       'modify_package')
        self.fill_field(by.By.ID, 'id_name', 'PostgreSQL')
        self.driver.find_element_by_xpath(c.InputSubmit).click()

        self.check_element_on_page(by.By.XPATH,
                                   c.AppPackageDefinitions.format(
                                       'PostgreSQL'))

    @utils.ordered
    def test_modify_package_add_tag(self):
        """Test check ability to add file in composed service

        Scenario:
            1. Navigate to 'Package Definitions' page
            2. Click on "Compose Service"  and create new service
            3. Manage composed service: add file
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')
        self.select_action_for_package('PostgreSQL',
                                       'modify_package')

        self.fill_field(by.By.ID, 'id_tags', 'TEST_TAG')
        self.modify_package('tags', 'TEST_TAG')

        self.navigate_to('Application_Catalog')
        self.go_to_submenu('Applications')
        self.select_and_click_action_for_app('details', self.postgre_id)
        self.assertIn('TEST_TAG',
                      self.driver.find_element_by_xpath(
                          c.TagInDetails).text)

    @utils.ordered
    def test_download_package(self):
        """Test check ability to download package from repository

        Scenario:
            1. Navigate to 'Package Definitions' page
            2. Select PostgreSQL package and click on "More>Download Package"
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')

        self.select_action_for_package('PostgreSQL', 'more')
        self.select_action_for_package('PostgreSQL', 'download_package')

    @utils.ordered
    def test_check_toggle_enabled_package(self):
        """Test check ability to make package active or inactive

        Scenario:
            1. Navigate to 'Package Definitions' page
            2. Select some package and make it inactive ("More>Toggle Active")
            3. Check that package is inactive
            4. Select some package and make it active ("More>Toggle Active ")
            5. Check that package is active
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')

        self.select_action_for_package('PostgreSQL', 'more')
        self.select_action_for_package('PostgreSQL', 'toggle_enabled')

        self.check_package_parameter('PostgreSQL', 'Active', 'False')

        self.select_action_for_package('PostgreSQL', 'more')
        self.select_action_for_package('PostgreSQL', 'toggle_enabled')

        self.check_package_parameter('PostgreSQL', 'Active', 'True')

    @utils.ordered
    def test_check_toggle_public_package(self):
        """Test check ability to make package active or inactive

        Scenario:
            1. Navigate to 'Package Definitions' page
            2. Select some package and make it inactive ("More>Toggle Public")
            3. Check that package is unpublic
            4. Select some package and make it active ("More>Toggle Public ")
            5. Check that package is public
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')

        self.select_action_for_package('PostgreSQL', 'more')
        self.select_action_for_package('PostgreSQL', 'toggle_public_enabled')

        self.check_package_parameter('PostgreSQL', 'Public', 'False')

        self.select_action_for_package('PostgreSQL', 'more')
        self.select_action_for_package('PostgreSQL', 'toggle_public_enabled')

        self.check_package_parameter('PostgreSQL', 'Public', 'True')

    @utils.ordered
    def test_check_info_about_app(self):
        """Test checks that information about app is available and truly.

        Scenario:
            1. Navigate to 'Application Catalog > Applications' panel
            2. Choose some application and click on 'More info'
            3. Verify info about application
        """
        self.go_to_submenu('Applications')
        self.select_and_click_action_for_app('details', self.mockapp_id)

        self.assertEqual('MockApp for webUI tests',
                         self.driver.find_element_by_xpath(
                             "//div[@class='app-description']").text)
        self.driver.find_element_by_link_text('Requirements').click()
        self.driver.find_element_by_link_text('License').click()

    @utils.ordered
    def test_check_search_option(self):
        """Test checks that 'Search' option is operable.

        Scenario:
            1. Navigate to 'Application Catalog > Applications' panel
            2. Set search criterion in the search field(e.g 'PostgreSQL')
            3. Click on 'Filter' and check result
        """
        self.go_to_submenu('Applications')
        self.fill_field(by.By.CSS_SELECTOR, 'input.form-control', 'PostgreSQL')
        self.driver.find_element_by_id('apps__action_filter').click()

        self.check_element_on_page(by.By.XPATH,
                                   c.App.format('PostgreSQL'))
        self.check_element_not_on_page(by.By.XPATH,
                                       c.App.format('MockApp'))

    @utils.ordered
    def test_filter_by_category(self):
        """Test checks ability to filter applications by category
        in Application Catalog page

        Scenario:
            1. Navigate to 'Application Catalog' panel
            2. Select 'Databases' category in 'App Category' dropdown menu
            3. Verify that PostgreSQL is shown
            4. Select 'Web' category in
            'App Category' dropdown menu
            5. Verify that MockApp is shown
        """
        self.go_to_submenu('Applications')
        self.driver.find_element_by_xpath(
            c.CategorySelector.format('All')).click()
        self.driver.find_element_by_link_text('Databases').click()

        self.check_element_on_page(by.By.XPATH, c.App.format('PostgreSQL'))

        self.driver.find_element_by_xpath(
            c.CategorySelector.format('Databases')).click()
        self.driver.find_element_by_link_text('Web').click()

        self.check_element_on_page(by.By.XPATH, c.App.format('MockApp'))

    @utils.ordered
    def test_check_option_switch_env(self):
        """Test checks ability to switch environment and add app in other env

        Scenario:
            1. Navigate to 'Application Catalog>Environments' panel
            2. Create environment 'env1'
            3. Create environment 'env2'
            4. Navigate to 'Application Catalog>Application Catalog'
            5. Click on 'Environment' panel
            6. Switch to env2
            7. Add application in env2
            8. Navigate to 'Application Catalog>Environments'
            and go to the env2
            9. Check that added application is here
        """
        self.go_to_submenu('Environments')
        self.create_environment('env1')
        self.go_to_submenu('Environments')
        self.check_element_on_page(by.By.LINK_TEXT, 'env1')
        self.create_environment('env2')
        self.go_to_submenu('Environments')
        self.check_element_on_page(by.By.LINK_TEXT, 'env2')

        env_id = self.get_element_id('env2')

        self.go_to_submenu('Applications')
        self.driver.find_element_by_xpath(
            ".//*[@id='environment_switcher']/a").click()

        self.driver.find_element_by_link_text("env2").click()

        self.select_and_click_action_for_app(
            'add', '{0}/{1}'.format(self.mockapp_id, env_id))

        self.fill_field(by.By.NAME, '0-name', 'TestA')
        self.driver.find_element_by_xpath(
            c.ButtonSubmit).click()

        self.driver.find_element_by_xpath(c.InputSubmit).click()
        self.select_from_list('osImage', self.image.name)
        self.driver.find_element_by_xpath(c.InputSubmit).click()

        self.driver.find_element_by_xpath(c.InputSubmit).click()

        self.check_element_on_page(by.By.LINK_TEXT, 'TestA')

    @utils.ordered
    def test_modify_description(self):
        """Test check ability to change description of the package

        Scenario:
            1. Navigate to 'Package Definitions' page
            2. Select package and click on 'Modify Package'
            3. Change description
        """
        self.navigate_to('Manage')
        self.go_to_submenu('Package Definitions')
        self.select_action_for_package('MockApp',
                                       'modify_package')

        self.modify_package('description', 'New Description')

        self.navigate_to('Application_Catalog')
        self.go_to_submenu('Applications')
        self.assertEqual('New Description',
                         self.driver.find_element_by_xpath(
                             c.MockAppDescr).text)