"""Relative Norm Distance (RND) metric implementation."""
import numpy as np
from typing import Any, Callable, Dict, List, Tuple, Union

from wefe.utils import cosine_similarity
from wefe.query import Query
from wefe.models.base_model import BaseModel
from wefe.metrics.base_metric import BaseMetric
from wefe.preprocessing import get_embeddings_from_query


class RND(BaseMetric):
    """A implementation of Relative Norm Distance (RND).

    It measures the relative strength of association of a set of neutral words
    with respect to two groups.

    References
    ----------
    Nikhil Garg, Londa Schiebinger, Dan Jurafsky, and James Zou.
    Word embeddings quantify 100 years of gender and ethnic stereotypes.
    Proceedings of the National Academy of Sciences, 115(16):E3635–E3644,2018.
    """

    metric_template = (2, 1)
    metric_name = "Relative Norm Distance"
    metric_short_name = "RND"

    def __calc_distance(
        self, vec1: np.ndarray, vec2: np.ndarray, distance_type: str = "norm",
    ) -> float:
        if distance_type == "norm":
            return np.linalg.norm(np.subtract(vec1, vec2))
        elif distance_type == "cos":
            # c = np.dot(vec1, vec2) / np.linalg.norm(vec1) / np.linalg.norm(vec2)
            c = cosine_similarity(vec1, vec2)
            return abs(c)
        else:
            raise Exception(
                'Parameter distance_type can be either "norm" or "cos". '
                "Given: {} ".format(distance_type)
            )

    def __calc_rnd(
        self,
        target_0: np.ndarray,
        target_1: np.ndarray,
        attribute: np.ndarray,
        attribute_words: list,
        distance_type: str,
        average_distances: bool,
    ) -> Tuple[float, Dict[str, float]]:

        # calculates the average wv for the group words.
        target_1_avg_vector = np.average(target_0, axis=0)
        target_2_avg_vector = np.average(target_1, axis=0)

        sum_of_distances = 0.0
        distance_by_words = {}

        for attribute_word_index, attribute_embedding in enumerate(attribute):

            # calculate the distance
            current_distance = self.__calc_distance(
                attribute_embedding, target_1_avg_vector, distance_type=distance_type,
            ) - self.__calc_distance(
                attribute_embedding, target_2_avg_vector, distance_type=distance_type,
            )

            # add the distance of the neutral word to the accumulated
            # distances.
            sum_of_distances += current_distance
            # add the distance of the neutral word to the list of distances
            # by word
            distance_by_words[attribute_words[attribute_word_index]] = current_distance

        sorted_distances_by_word = {
            k: v for k, v in sorted(distance_by_words.items(), key=lambda item: item[1])
        }

        if average_distances:
            # calculate the average of the distances and return
            mean_distance = sum_of_distances / len(distance_by_words)
            return mean_distance, sorted_distances_by_word

        return sum_of_distances, sorted_distances_by_word

    def run_query(
        self,
        query: Query,
        word_embedding: BaseModel,
        distance: str = "norm",
        average_distances: bool = True,
        lost_vocabulary_threshold: float = 0.2,
        preprocessors: List[Dict[str, Union[str, bool, Callable]]] = [{}],
        strategy: str = "first",
        normalize: bool = False,
        warn_not_found_words: bool = False,
        *args: Any,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Calculate the RND metric over the provided parameters.

        Parameters
        ----------
        query : Query
            A Query object that contains the target and attribute sets to be tested.

        word_embedding_model : BaseModel
            An object containing a word embedding model.

        distance : str, optional
            Specifies which type of distance will be calculated. It could be:
            {norm, cos} , by default 'norm'.

        average_distances : bool, optional
            Specifies wheter the function averages the distances at the end of
            the calculations, by default True

        lost_vocabulary_threshold : float, optional
            Specifies the proportional limit of words that any set of the query is
            allowed to lose when transforming its words into embeddings.
            In the case that any set of the query loses proportionally more words
            than this limit, the result values will be np.nan, by default 0.2

        preprocessors : List[Dict[str, Union[str, bool, Callable]]]
            A list with preprocessor options.

            A dictionary of preprocessing options is a dictionary that specifies what
            transformations will be made to each word prior to being searched in the
            word embedding model vocabulary.
            For example, `{'lowecase': True, 'strip_accents': True}` allows you to
            transform the words to lowercase and remove the accents and then search
            for them in the model.
            Note that an empty dictionary `{}` indicates that no transformation
            will be made to any word.

            A list of these preprocessor options will allow you to search for several
            variants of the words (depending on the search strategy) into the model.
            For example `[{}, {'lowecase': True, 'strip_accents': True}]` allows you
            to search for each word, first, without any transformation and then,
            transformed to lowercase and without accents.

            The available word preprocessing options are as follows (it is not necessary
            to put them all):

            - `lowercase`: `bool`. Indicates if the words are transformed to lowercase.
            - `uppercase`: `bool`. Indicates if the words are transformed to uppercase.
            - `titlecase`: `bool`. Indicates if the words are transformed to titlecase.
            - `strip_accents`: `bool`, `{'ascii', 'unicode'}`: Specifies if the accents
                                of the words are eliminated. The stripping type can be
                                specified. True uses 'unicode' by default.
            - `preprocessor`: `Callable`. It receives a function that operates on each
                            word. In the case of specifying a function, it overrides
                            the default preprocessor (i.e., the previous options
                            stop working).
            by default [{}].

        strategy : str, optional
            The strategy indicates how it will use the preprocessed words: 'first' will
            include only the first transformed word found. all' will include all
            transformed words found, by default "first".

        normalize : bool, optional
            True indicates that embeddings will be normalized, by default False

        warn_not_found_words : bool, optional
            Specifies if the function will warn (in the logger)
            the words that were not found in the model's vocabulary
            , by default False.

        Returns
        -------
        Dict[str, Any]
            A dictionary with the query name, the resulting score of the metric,
            and a dictionary with the distances of each attribute word
            with respect to the target sets means.

        Examples
        --------
        >>> from wefe.metrics import RND
        >>> from wefe.query import Query
        >>> from wefe.utils import load_test_model
        >>>
        >>> # define the query
        >>> query = Query(
        ...     target_sets=[
        ...         ["female", "woman", "girl", "sister", "she", "her", "hers",
        ...          "daughter"],
        ...         ["male", "man", "boy", "brother", "he", "him", "his", "son"],
        ...     ],
        ...     attribute_sets=[
        ...         [
        ...             "home", "parents", "children", "family", "cousins", "marriage",
        ...             "wedding", "relatives",
        ...         ],
        ...     ],
        ...     target_sets_names=["Female terms", "Male Terms"],
        ...     attribute_sets_names=["Family"],
        ... )
        >>>
        >>> # load the model (in this case, the test model included in wefe)
        >>> model = load_test_model()
        >>>
        >>> # instance the metric and run the query
        >>> RND().run_query(query, model) # doctest: +SKIP
        {'query_name': 'Female terms and Male Terms wrt Family',
         'result': 0.030381828546524048,
         'rnd': 0.030381828546524048,
         'distances_by_word': {'wedding': -0.1056304,
                               'marriage': -0.10163283,
                               'children': -0.068374634,
                               'parents': 0.00097084045,
                               'relatives': 0.0483346,
                               'family': 0.12408042,
                               'cousins': 0.17195654,
                               'home': 0.1733501}}
        >>>
        >>> # if you want the embeddings to be normalized before calculating the metrics
        >>> # use the normalize parameter as True before executing the query.
        >>> RND().run_query(query, model, normalize=True) # doctest: +SKIP
        {'query_name': 'Female terms and Male Terms wrt Family',
         'result': -0.006278775632381439,
         'rnd': -0.006278775632381439,
         'distances_by_word': {'children': -0.05244279,
                               'wedding': -0.04642248,
                               'marriage': -0.04268837,
                               'parents': -0.022358716,
                               'relatives': 0.005497098,
                               'family': 0.023389697,
                               'home': 0.04009247,
                               'cousins': 0.044702888}}
        >>>
        >>> # if you want to use cosine distance instead of euclidean norm
        >>> # use the distance parameter as 'cos' before executing the query.
        >>> RND().run_query(query, model, normalize=True, distance='cos') # doctest: +SKIP
        {'query_name': 'Female terms and Male Terms wrt Family',
         'result': 0.03643466345965862,
         'rnd': 0.03643466345965862,
         'distances_by_word': {'cousins': -0.035989374,
                               'home': -0.026971221,
                               'family': -0.009296179,
                               'relatives': 0.015690982,
                               'parents': 0.051281124,
                               'children': 0.09255883,
                               'marriage': 0.09959312,
                               'wedding': 0.104610026}}
        """
        # check the types of the provided arguments (only the defaults).
        self._check_input(query, word_embedding)

        # transform query word sets into embeddings
        embeddings = get_embeddings_from_query(
            model=word_embedding,
            query=query,
            lost_vocabulary_threshold=lost_vocabulary_threshold,
            preprocessors=preprocessors,
            strategy=strategy,
            normalize=normalize,
            warn_not_found_words=warn_not_found_words,
        )

        # if there is any/some set has less words than the allowed limit,
        # return the default value (nan)
        if embeddings is None:
            return {
                "query_name": query.query_name,
                "result": np.nan,
                "rnd": np.nan,
                "distances_by_word": {},
            }

        # get the targets and attribute sets transformed into embeddings.
        target_sets, attribute_sets = embeddings

        # get only the embeddings of the sets.
        target_embeddings = list(target_sets.values())
        attribute_embeddings = list(attribute_sets.values())

        target_0_embeddings = np.array(list(target_embeddings[0].values()))
        target_1_embeddings = np.array(list(target_embeddings[1].values()))
        attribute_0_embeddings = np.array(list(attribute_embeddings[0].values()))

        # get a list with the transformed attribute words
        attribute_0_words = list(attribute_embeddings[0].keys())

        rnd, distances_by_word = self.__calc_rnd(
            target_0_embeddings,
            target_1_embeddings,
            attribute_0_embeddings,
            attribute_0_words,
            distance,
            average_distances,
        )

        return {
            "query_name": query.query_name,
            "result": rnd,
            "rnd": rnd,
            "distances_by_word": distances_by_word,
        }
