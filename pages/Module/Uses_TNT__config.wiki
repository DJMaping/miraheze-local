local cfg = {} -- Don’t touch this line.

-- Subpage blacklist: these subpages will not be categorized (except for the
-- error category, which is always added if there is an error).
-- For example “Template:Foo/doc” matches the `doc = true` rule, so it will have
-- no categories. “Template:Foo” and “Template:Foo/documentation” match no rules,
-- so they *will* have categories. All rules should be in the
--   ['<subpage name>'] = true,
-- format.
cfg['subpage_blacklist'] = {
	['doc'] = true,
	['sandbox'] = true,
	['sandbox2'] = true,
	['testcases'] = true,
}

-- Allow wishes: whether wishes for conversion to use [[Module:TNT]]
-- are implicitly allowed.
-- If `true`, calls with zero parameters are valid, and considered to be wishes:
-- The box’s text is “This template should use [[Module:TNT]]”, and
-- `cfg['wish_category']` is added.
-- If `false`, such calls are invalid unless the `|wish=` parameter is truthy,
-- an error message appears, and `cfg['error_category']` is added.
cfg['allow_wishes'] = false

-- Default category: this category is added if the module call contains errors
-- (e.g. no module listed). A category name without namespace, or nil
-- to disable categorization (not recommended).
cfg['error_category'] = nil

-- Wish category: this category is added if no module is listed, and wishes are
-- allowed. (Not used if wishes are not allowed.) A category name without
-- namespace, or nil to disable categorization.
cfg['wish_category'] = nil

-- Default category: this category is added if no custom category is specified
-- in module/template call. A category name without namespace, or nil
-- to disable categorization.
cfg['default_category'] = 'Templates using Module:TNT for internationalisation'

-- Logo link: the link for the logo text. Set to nil to disable linking.
cfg["logo_link"] = 'Special:MyLanguage/WP:TNT'

return cfg -- Don’t touch this line.