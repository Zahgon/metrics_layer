import functools
import json
from collections import Counter
from contextlib import contextmanager
from typing import List, Union

from metrics_layer.core.exceptions import (
    AccessDeniedOrDoesNotExistException,
    QueryError,
)

from .dashboard import Dashboard
from .field import Field
from .join_graph import JoinGraph
from .model import AccessGrant, Model
from .topic import Topic
from .view import View


class Project:
    """
    Higher level abstraction for the whole project
    """

    def __init__(
        self,
        models: list,
        views: list,
        dashboards: list = [],
        topics: list = [],
        looker_env: Union[None, str] = None,
        connection_lookup: dict = {},
        manifest=None,
        commit_hash=None,
        conversion_errors: list = [],
    ):
        self._models = models
        self._views = self._handle_join_as_duplication(views, topics)
        self._dashboards = dashboards
        self._topics = topics
        self.looker_env = looker_env
        self.connection_lookup = connection_lookup
        self.manifest = manifest
        self.manifest_exists = manifest and manifest.exists()
        self._user = None
        self._connection_schema = None
        self._timezone = None
        self._required_access_filter_user_attributes = []
        self._join_graph = None
        self.commit_hash = commit_hash
        self._conversion_errors = conversion_errors

    def __repr__(self):
        text = "models" if len(self._models) != 1 else "model"
        return f"<Project {len(self._models)} {text} user={self._user}>"

    def __hash__(self):
        user_str = "" if not self._user else json.dumps(self._user, sort_keys=True)
        return self._content_hash + hash(user_str)

    def id(self):
        pass

    def refresh_cache(self):
        # Clear LRU Caches
        pass

    @functools.cached_property
    def _content_hash(self):
        pass

    def set_user(self, user: dict):
        self._user = user

    def set_connection_schema(self, schema: str):
        pass

    def set_timezone(self, timezone: str):
        pass

    def set_required_access_filter_user_attributes(self, user_attribute_names: List[str]):
        pass

    def replace_field(self, field: dict, view_name: str, refresh_cache: bool = True):
        pass

    def add_field(self, field: dict, view_name: str, refresh_cache: bool = True):
        pass

    def remove_field(self, field_name: str, view_name: str, refresh_cache: bool = True):
        pass

    @property
    def timezone(self):
        if self._timezone:
            return self._timezone
        timezones = list(set(m.timezone for m in self.models() if m.timezone))
        if len(timezones) == 1:
            return timezones[0]
        elif len(timezones) > 1:
            raise QueryError(
                "Multiple timezones found in models, please specify only one timezone across models"
            )
        return None

    @property
    def join_graph(self):
        pass

    def _handle_join_as_duplication(self, views: list, topics: list = []):
        pass

    @contextmanager
    def replace_objects(self, replaced_objects: list):
        pass

    def validate_with_replaced_objects(
        self,
        replaced_objects: list,
        views_must_be_in_topics: bool = False,
        validate_topics: bool = True,
    ):
        pass

    def _error(self, error: str, extra: dict = {}):
        # For project level errors we cannot attribute a line or column
        return {
            **extra,
            "message": error,
            "line": None,
            "column": None,
            "reference_type": "project",
            "reference_id": None,
        }

    def validate(self, views_must_be_in_topics: bool = False, validate_topics: bool = True):
        metrics_must_have_dates = views_must_be_in_topics
        all_errors = [] + self._conversion_errors

        model_names = [model.name for model in self.models()]

        # Check for duplicate model names
        duplicate_models = [name for name, count in Counter(model_names).items() if count > 1]
        for model_name in duplicate_models:
            return [self._error(f"Duplicate model name: {model_name}. Model names must be unique.")]

        for model in self.models():
            try:
                all_errors.extend(model.collect_errors())
            except (QueryError, AccessDeniedOrDoesNotExistException) as e:
                # If we have an error building the model, we cannot continue
                return [self._error(str(e))]

        if validate_topics:
            topic_names = []
            try:
                topics = self.topics()
            except AccessDeniedOrDoesNotExistException as e:
                # If we have an error building the topics, we cannot continue
                return [self._error(str(e))]

            for topic in topics:
                topic_names.append(topic.name)
                try:
                    all_errors.extend(topic.collect_errors())
                except QueryError as e:
                    # If we have an error building the topic, we cannot continue
                    return [self._error(str(e))]

            # Check for duplicate topic names
            duplicate_topics = [name for name, count in Counter(topic_names).items() if count > 1]
            for topic_name in duplicate_topics:
                all_errors.append(
                    self._error(f"Duplicate topic name: {topic_name}. Topic names must be unique.")
                )

        if views_must_be_in_topics:
            views_in_topics = set(
                [v.name for topic in self.topics() for v in topic._views() + topic.from_view_references()]
            )
            for view in self.views():
                if view.name not in views_in_topics:
                    all_errors.append(view._error(None, f"View {view.name} is not in a topic"))

        try:
            all_errors.extend(self.join_graph.collect_errors())
        except QueryError as e:
            # If we have an error building the graph, we cannot continue
            # and no other errors will be relevant until this is fixed
            return [self._error(str(e))]

        for join_graph in self.join_graph.list_join_graphs():
            try:
                self.get_field_by_tag(tag_name="customer", join_graphs=(join_graph,))
            except QueryError as e:
                error_text = str(e).replace(" name ", " tag ").split("\n")[0]
                error_text += '. Only one field can have the tag "customer" per joinable graph.'
                all_errors.append(self._error(error_text))
            except Exception:
                pass

        for view in self.views():
            if len(self._required_access_filter_user_attributes) > 0:
                for user_attribute_name in self._required_access_filter_user_attributes:
                    if not view.access_filters:
                        all_errors.append(
                            view._error(
                                None,
                                (
                                    f"View {view.name} does not have any access filters, but an access filter"
                                    f" with user attribute {user_attribute_name} is required."
                                ),
                            )
                        )
                    elif all(af["user_attribute"] != user_attribute_name for af in view.access_filters):
                        all_errors.append(
                            view._error(
                                None,
                                (
                                    f"View {view.name} does not have an access filter with the required user"
                                    f" attribute {user_attribute_name}"
                                ),
                            )
                        )

            try:
                view.sql_table_name
            except QueryError as e:
                all_errors.append(view._error(None, str(e) + f" in the view {view.name}"))
            try:
                referenced_fields = view.referenced_fields()
            except (AccessDeniedOrDoesNotExistException, QueryError) as e:
                all_errors.append(view._error(None, str(e) + f" in the view {view.name}"))

            view_errors = view.collect_errors(metrics_must_have_dates=metrics_must_have_dates)

            for field in referenced_fields:
                if isinstance(field, tuple):
                    if "Warning: " in field[-1]:
                        field_name = field[0].name
                        field_reference = field[-1].replace("Warning: ", "")
                        prepend = "Warning: "
                    else:
                        field_name = field[0].name
                        field_reference = field[-1]
                        prepend = ""
                    all_errors.append(
                        view._error(
                            None,
                            (
                                f"{prepend}Could not locate reference {field_reference} in field"
                                f" {field_name} in view {view.name}"
                            ),
                        )
                    )
            all_errors.extend(view_errors)

        for dashboard in self.dashboards():
            errors = dashboard.collect_errors()
            all_errors.extend(errors)

        all_errors.extend(self._validate_dashboard_names())

        cleaned_errors, _seen = [], set([])
        for e in all_errors:
            if isinstance(e, dict) and e["message"] not in _seen:
                cleaned_errors.append(e)
                _seen.add(e["message"])

        return cleaned_errors

    def _validate_dashboard_names(self):
        # We need to make sure the unique identifiers for the dashboards are actually unique
        errors = []
        dashboard_names = [d.name for d in self.dashboards()]
        name_frequency = Counter(dashboard_names).most_common()
        for name, frequency in name_frequency:
            if frequency > 1:
                msg = f"Dashboard name {name} appears {frequency} times, make sure dashboard names are unique"
                errors.append(self._error(msg))
            else:
                break
        return errors

    def _all_dashboards(self):
        dashboards = []
        for d in self._dashboards:
            dashboard = Dashboard(d, project=self)
            user_allowed = self.can_access_dashboard(dashboard)
            if user_allowed:
                dashboards.append(dashboard)
        return dashboards

    def dashboards(self) -> list:
        return self._all_dashboards()

    def get_dashboard(self, dashboard_name: str) -> Model:
        pass

    def models(self, show_hidden: bool = True) -> list:
        models = []
        for m in self._models:
            model = Model(m, project=self)
            model_is_visible = show_hidden or model.hidden is False
            if self.can_access_model(model) and model_is_visible:
                models.append(model)
        return models

    def _all_models(self) -> List[Model]:
        """No permission checks are applied to this method BE CAREFUL"""
        return [Model(m, project=self) for m in self._models]

    def _model_exists(self, model_name: str) -> bool:
        return any(m.name == model_name for m in self._all_models())

    def get_model(self, model_name: str) -> Model:
        try:
            return next((m for m in self.models() if m.name == model_name))
        except StopIteration:
            raise AccessDeniedOrDoesNotExistException(
                f"Could not find or you do not have access to model {model_name}",
                object_name=model_name,
                object_type="model",
            )

    def topics(self, show_hidden: bool = True) -> list:
        topics = []
        for t in self._topics:
            topic = Topic(t, project=self)
            topic_is_visible = show_hidden or topic.hidden is False
            if self.can_access_topic(topic) and topic_is_visible:
                topics.append(topic)
        return topics

    def get_topic(self, topic_name: str) -> Topic:
        try:
            return next((t for t in self.topics() if t.name == topic_name))
        except StopIteration:
            raise AccessDeniedOrDoesNotExistException(
                f"Could not find or you do not have access to topic {topic_name}",
                object_name=topic_name,
                object_type="topic",
            )

    def access_grants(self):
        return [AccessGrant(g, model=m) for m in self._all_models() for g in m.access_grants]

    def get_access_grant(self, grant_name: str):
        try:
            return next((ag for ag in self.access_grants() if ag.name == grant_name))
        except StopIteration:
            raise QueryError(f"Could not find the access grant {grant_name} in your project.")

    def can_access_dashboard(self, dashboard: Dashboard):
        return self._can_access_object(dashboard)

    def can_access_topic(self, topic: Topic):
        try:
            return self._can_access_object(topic) and self.can_access_model(topic.model)
        except AccessDeniedOrDoesNotExistException as e:
            if self._model_exists(topic.model_name):
                # If we're not able to access the model, we can't access the topic
                return False
            else:
                # Otherwise, the model is named incorrectly, and we should raise the error
                raise e

    def can_access_view(self, view: View):
        try:
            return self._can_access_object(view) and self.can_access_model(view.model)
        except AccessDeniedOrDoesNotExistException as e:
            if self._model_exists(view.model_name):
                # If we're not able to access the model, we can't access the view
                return False
            else:
                # Otherwise, the model is named incorrectly, and we should raise the error
                raise e

    def can_access_model(self, model: Model):
        return self._can_access_object(model)

    def can_access_field(self, field):
        can_access_view = self.can_access_view(field.view)
        return self._can_access_object(field) and can_access_view

    def _can_access_object(self, obj):
        if self._user is not None:
            if obj.required_access_grants:
                decisions = []
                for grant_name in obj.required_access_grants:
                    grant = self.get_access_grant(grant_name)
                    user_attribute_value = self._user.get(grant.user_attribute)

                    if user_attribute_value is None:
                        decision = True
                    else:
                        decision = user_attribute_value in grant.allowed_values
                    decisions.append(decision)

                # We use all here because the condition between access conditions is AND
                return all(decisions)
        return True

    def _views_for_a_model(self, model_name: str, show_hidden: bool = True):
        return [v for v in self._all_views(show_hidden=show_hidden) if v.model_name == model_name]

    def _all_views(self, show_hidden: bool = True):
        views = []
        for v in self._views:
            view = View(v, project=self)
            view_is_visible = show_hidden or view.hidden is False
            if self.can_access_view(view) and view_is_visible:
                views.append(view)
        return views

    def views(self, model_name: Union[str, None] = None, show_hidden: bool = True) -> list:
        if model_name:
            return self._views_for_a_model(model_name, show_hidden)
        else:
            return self._all_views(show_hidden)

    def get_view(self, view_name: str, model_name: Union[str, None] = None) -> View:
        try:
            return next((v for v in self.views(model_name=model_name) if v.name == view_name))
        except StopIteration:
            raise AccessDeniedOrDoesNotExistException(
                f"Could not find or you do not have access to view {view_name}",
                object_name=view_name,
                object_type="view",
            )

    def get_joinable_views(self, view_name: str) -> List[str]:
        pass

    def get_joinable_views_including_topics(self, view_name: str) -> List[str]:
        joinable_no_topics = self.join_graph.get_joinable_view_names(view_name)
        joinable_from_topics = []
        for topic in self.topics():
            topic_view_names = [v.name for v in topic._views() + topic.from_view_references()]
            if view_name in topic_view_names:
                joinable_from_topics.extend(topic_view_names)
        return list(set(joinable_no_topics + joinable_from_topics))

    def sets(self, view_name: Union[str, None] = None):
        if view_name:
            try:
                views = [self.get_view(view_name)]
            except AccessDeniedOrDoesNotExistException:
                views = []
        else:
            views = self.views()

        all_sets = []
        for view in views:
            all_sets.extend(view.list_sets())
        return all_sets

    def get_set(self, set_name: str, view_name: Union[str, None] = None):
        if view_name:
            sets = self.sets(view_name=view_name)
        else:
            sets = self.sets()
        return next((s for s in sets if s.name == set_name), None)

    @functools.lru_cache(maxsize=None)
    def fields(
        self,
        view_name: Union[str, None] = None,
        topic_label: Union[str, None] = None,
        show_hidden: bool = True,
        expand_dimension_groups: bool = False,
        model_name: Union[str, None] = None,
    ) -> list:
        if view_name is None and topic_label is None:
            return self._all_fields(show_hidden, expand_dimension_groups, model_name)
        elif topic_label is not None and view_name is None:
            return self._topic_fields(topic_label, show_hidden, expand_dimension_groups, model_name)
        elif view_name is not None and topic_label is None:
            return self._view_fields(view_name, show_hidden, expand_dimension_groups)
        else:
            raise QueryError(
                "Ambiguous query: you must specify either a view_name or a topic_label, but not both."
            )

    def _all_fields(
        self,
        show_hidden: bool,
        expand_dimension_groups: bool,
        model_name: Union[str, None] = None,
    ):
        return [
            f
            for v in self.views(model_name=model_name, show_hidden=show_hidden)
            for f in v.fields(show_hidden, expand_dimension_groups)
        ]

    def _topic_fields(
        self,
        topic_label: str,
        show_hidden: bool = True,
        expand_dimension_groups: bool = False,
        model_name: Union[str, None] = None,
    ):
        topic = self.get_topic(topic_label)
        if not topic:
            plus_model = f" in model {model_name}" if model_name else ""
            raise QueryError(f"Could not find a topic matching the label {topic_label}{plus_model}")
        return [f for v in topic._views() for f in v.fields(show_hidden, expand_dimension_groups)]

    def _view_fields(self, view_name: str, show_hidden: bool = True, expand_dimension_groups: bool = False):
        view = self.get_view(view_name)
        if not view:
            raise QueryError(f"Could not find a view matching the name {view_name}")
        return view.fields(show_hidden, expand_dimension_groups)

    def joinable_fields(self, field_list: list, expand_dimension_groups: bool = False):
        pass

    @functools.lru_cache(maxsize=None)
    def get_field(
        self, field_name: str, view_name: Union[str, None] = None, model_name: Union[str, None] = None
    ) -> Field:
        field_name, view_name = self._parse_field_and_view_name(field_name, view_name)

        fields = self.fields(view_name=view_name, expand_dimension_groups=True, model_name=model_name)
        matching_fields = [f for f in fields if f.equal(field_name)]
        return self._matching_field_handler(matching_fields, field_name, view_name)

    def get_mapped_field(self, field_name: str, model: Model):
        pass

    @functools.lru_cache(maxsize=None)
    def get_field_by_name(
        self, field_name: str, view_name: Union[str, None] = None, model_name: Union[str, None] = None
    ):
        field_name, view_name = self._parse_field_and_view_name(field_name, view_name)
        fields = self.fields(view_name=view_name, expand_dimension_groups=False, model_name=model_name)
        matching_fields = [f for f in fields if f.name == field_name]
        return self._matching_field_handler(matching_fields, field_name, view_name)

    @functools.lru_cache(maxsize=None)
    def get_field_by_tag(
        self,
        tag_name: str,
        view_name: Union[str, None] = None,
        join_graphs: Union[tuple, None] = None,
        model_name: Union[str, None] = None,
    ):
        tag_options = {tag_name, f"{tag_name}s"} if tag_name[-1] != "s" else {tag_name, tag_name[:-1]}
        fields = self.fields(view_name=view_name, expand_dimension_groups=True, model_name=model_name)
        matching_fields = [f for f in fields if f.tags and any(t in tag_options for t in f.tags)]
        if join_graphs:
            matching_fields = [f for f in matching_fields if any(j in f.join_graphs() for j in join_graphs)]
        return self._matching_field_handler(matching_fields, tag_name, view_name)

    def does_field_exist(
        self,
        field_name: str,
        view_name: Union[str, None] = None,
        model_name: Union[str, None] = None,
    ):
        pass

    def _parse_field_and_view_name(self, field_name: str, view_name: Union[str, None]):
        # Handle the case where the view syntax is passed: view_name.field_name
        if "." in field_name:
            specified_view_name, field_name = Field.field_name_parts(field_name)
            if view_name and specified_view_name != view_name:
                raise QueryError(
                    f"You specified two different view names {specified_view_name} and {view_name}"
                )
            view_name = specified_view_name
        return field_name.lower(), view_name

    def _matching_field_handler(self, matching_fields: list, field_name: str, view_name: Union[str, None]):
        if len(matching_fields) == 1:
            return matching_fields[0]

        elif len(matching_fields) > 1:
            matching_names = [f.id() for f in matching_fields]
            view_text = f", in view {view_name}" if view_name else ""
            err_msg = (
                f"Multiple fields found for the name {field_name}{view_text}"
                f" - those fields were {matching_names}\n\nPlease specify a "
                "view name like this: 'view_name.field_name' "
                "\n\nor change the names of the fields to ensure uniqueness"
            )
            raise QueryError(err_msg)
        elif field_name == "count" and view_name:
            definition = {"type": "count", "name": "count", "field_type": "measure"}
            return Field(definition, view=self.get_view(view_name))
        else:
            err_msg = f"Field {field_name} not found"
            if view_name:
                err_msg += f" in view {view_name}"
            err_msg += ", please check that this field exists AND that you have access to it. \n\n"
            err_msg += "If this is a dimension group specify the group parameter, if not already specified, "
            err_msg += "for example, with a dimension group named 'order' with timeframes: [raw, date, month]"
            err_msg += " specify 'order_raw' or 'order_date' or 'order_month'"
            raise AccessDeniedOrDoesNotExistException(err_msg, object_name=field_name, object_type="field")

    def resolve_dbt_ref(self, ref_name: str):
        # This just returns the table name, assuming the schema will be set in the connection
        pass

    @staticmethod
    def deduplicate_fields(field_list: list):
        pass
