# Copyright 2020 Juneau
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A series of utility functions used throughout Juneau.
"""


def clean_notebook_name(nb_name):
    """
    Cleans the notebook name by removing the .ipynb extension, removing hyphens,
    and removing underscores.
    Example:
        >>> nb = "My-Awesome-Notebook.ipynb"
        >>> handler = JuneauHandler()
        >>> # Receive a PUT with `nb`
        >>> print(handler._clean_notebook_name())
        >>> # prints "MyAwesomeNotebook"
    Returns:
        A string that is cleaned per the requirements above.
    """
    nb_name = nb_name.replace('.ipynb', '').replace('-', '').replace('_', '')
    nb_name = nb_name.split("/")
    if len(nb_name) > 2:
        nb_name = nb_name[-2:]
    nb_name = "".join(nb_name)
    return nb_name[-25:]
