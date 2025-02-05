% Understanding Models Understanding Optionality
% [Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)
% $d_{model}$

The last five years have shown us that Large Language Models can
effectively write programs in many domains. This is an impressive
capability given that writing programs involves having a working
understanding of many aspects of their semantics. But though we know
that these large models understand programs to an extent, we still
don’t know what form that understanding takes; where it has a deep
understanding and where it uses heuristic reasoning, how it represents
program knowledge, and what kinds of situations will challenge its
capabilities.

Fortunately, recent work in model interpretability and
representation engineering has produced promising results
which give hope towards understanding more and more of the
internal thought processes of LLMs. Here at dmodel , we can
think of no better place to apply these new techniques than
program understanding, where there are many abstract
properties that can be symbolically determined. The vast work
done in programming language theory over the past hundred
years provides many tools for scaling an understanding of the
internal thought processes of language models as they write
code.

In that spirit, we wanted to start with a simple property that comes
up in every programming languages, value optionality. Optional values
are represented differently across languages, null pointers in C++ or
Java, with explicit option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be optional is necessary for even
their most basic uses, and misunderstanding where they are optional
can often be a source of bugs, like a null pointer dereference.

Do our models understand when a value is optional? They must, to be
able to write code that deals with optional values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.

## Which Models Understand Optionality?

Before attempting to measure how models understand optionality on a
low level, we wanted to first be able to measure their optionality
understanding on a high level. After all, we could spend forever
looking for a concept of optionality in a model that doesn’t actually
exist. So we first measure how well different completion models can
complete simple programs that require an understanding of
optionality. Then, we have an idea of which models to search for an
internal optionality concept.

To test these models for optionality understanding, we constructed 15
partial program tests. Here’s one of them:

*Test 4*:
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```

This partial program is only four lines, with type annotations. A
some_numbers array is created that includes positive numbers, negative
numbers, and None values, giving it type `Optional[int]`. A result
list is constructed to give the model a sense of how dataflow should
work, and then a for loop is started, looping over some_numbers.

The program is constructed such that there are a very limited number
of valid next lines in the program, and all of them demonstrate some
knowledge of the concept of optionality.^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.
The simplest way to do this is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. Since this is a pretty small space
of valid next lines, and all of them imply some understanding that
`num` may not be an `int`, we can use this program to test models for
optionality understanding by asking them to complete the program
another lines, then see if they produce something that matches these
valid lines with the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]

This test is on the simpler side of optionality understanding, but
there are several ways to challenge the model a bit more, by adding
more layers of indirection between the source and sink of optional
values. This allows us to see how well different models can track
optionality across the program.

We can also test how well models understand type annotations
separately; since Python is a gradually typed language, most of the
Python code used as training data operates in an untyped fashion, so
models may understand the dynamic flow of optional values but not
their static type annotations. Test 5 below tests the models understanding of
Optionality types annotations.^[The trailing colon makes a type expression
the only valid completion; function declarations with a colon and no
type, like `def fn(x:)` are not valid python. Since we’ve already seen
a usage of `get_square` that is passed a None value, it wouldn’t be
type-valid to complete the program with just `int`. So a model can be
tested on its understanding of `Optional` annotations by seeing if its
completion of the partial program includes `Optional[int]`.]

*Test 5*:
```python
def program_48() -> None:
  number: Optional[int] = None
  square = get_square(number)
  if square is not None:
    print(f"Square of the number is {square}")
  else:
    print("No number provided to square")

def get_square(number:
```

We start to measure the difficulty of these tests by measuring how
models of different sizes do on them. For many tests in this post, we
use the Pythia models, as they are available in a large variety of
sizes and training lengths. For measuring performance at larger sizes,
we've included Qwen2.5-Coder-32B, Llama 3.1 405B Instruct, and
DeepSeek-V3 (671B). Below, you can see the number of passing tests for
each model.

*Figure 1*
![A bar graph showing how several sizes of model perform on the
 high-level optionality tests](images/hl_model_results.svg)

Next, we want to know how the amount of training affects model
performance on these tests. Luckily, Pythia also provides models at
different training steps, all the way from step 2 to step
143000. Below we can see how Pythia 6.9b performs on the tests during
training:

*Figure 2*
![A line graph showing how the performance of the Pythia
6.9 model changes during training](images/hl_revision_results.svg)

Again, we see that while the model generally gets better at passing
these tests during training, the performance is not always increasing.


## Morally vs Technically Correct

*Figure 3*
![A graph showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that shows true
understanding.](images/hl_mypy_vs_grep.svg)

## Designing Prompts to Extract Optionality Activations

At this point, we’ve figured out how to roughly measure optionality
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. To do this, we’re going to bring in some ideas described
in Zhou et al’s paper [“Representation Engineering: A Top-Down Approach
to AI Transparency”](https://arxiv.org/abs/2310.01405).

As language models predict each token in a text, they run their tuned
circuits over all the previous text. Tokens are first embedded into a
high-dimensional “token space”, and each layer of the transformer
model is made up of many parallel circuits which transform the
previous layers output into new embeddings in a new space. Each layer
can look not just at the output of the layer directly previous, but
actually all previous layers, through a channel called a residual
stream.

The paper presents two main approaches to interpreting a language
model; circuit-based, and representation-based. Circuit based
interpretability aims to pair down the network to a key set of
circuits which are sufficient to complete a particular task; this
allows practitioners to point to a particular part of the model and
say “this is where \<task\> is done”, much like neuroscientists assign
functionality to different parts of our brain.

On the other hand, representation-based interpretability looks at the
activation values across the network, and how they vary based on
different inputs, to extract “representations” of particular
concepts. The paper shows how representations can be extracted for
concepts like “happiness”, “honesty”, and “fairness”. First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with “Pretend you’re a dishonest person. The Eiffel Tower is” and
“Pretend you’re an honest person. The Eiffel Tower isr”. Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is present in the model at any given time (for honesty, this
can be a lie-detector). They can also use it, and similar techniques,
to control the amount of the concept in a response, making it more or
less honest, or more or less fair.

![An excerpt from Zhou et al showing the reading outputs for several
 concepts](images/zhou.png)

In our setting, we were able to avoid dealing with the ambiguities of
natural language by only prompting with code. We decided to stick to
analyzing the optionality of individual variable occurrences, instead
of analyzing every expression. Specifically, we tried to capture the
concept “the variable I just generated refers to an optional
quantity”, so our prompts looked like:

```python
def program_1() -> None:
  def find_value(data: List[int], target: int) -> Optional[int]:
    for value in data:
      if value == target:
      return value
    return None

  data = [1, 2, 3, 4, 5]
  target = 3
  result = find_value(data, target)
  if result
```

To generate these kinds of prompts, we started by asking a few
different chat models to generate for us programs that made use of
optionality. We prompted each model with:

```
Generate me 100 typed python programs that use the optional type,
along with type annotations for any undefined functions that they
use. Make sure that the programs are unique, and each involves at
least eight lines of logic. Number each program from 1 to 100. Please
put all the programs in a single file, with a main function that tests
each. Don't include any text before or after the code, just the
code. I will be using mypy with the --strict option to check the code.
```

We queried o1, o1-mini, deepseek-coder, and claude-sonnet using this
prompt, and then combined programs from the output of all of them into
a single file. Then, we took every function and class in the resulting
code file, and created a file with it and any recursive dependencies
and imports from the file. Finally, we took each variable read
occurrence in each function, and generated a prompt with the tokens up
to and including that variable read, and labeled it with whether or
not the mypy-inferred type is an Optional.

## Reading Vector Extraction

To start, let's look at how previous works have extracted reading
vectors from sample activations. In the Zhou representation
engineering paper, the authors extract a reading vector from the
contrastive pairs of activations using principal component
analysis.

First, they take each pair of honest and dishonest promptings for the
same stimulus, and get the difference between them, creating a set of
contrast vectors. They randomly flip some of these contrast vectors,
so that overall the set will vary a lot along the direction of the
contrast.  Since PCA assumes that the data is centered around the
origin, they then took the mean of all these vectors, and translated
all the vectors backwards along the mean vector, to create a set with
the same variances but centered around the origin.

Next, they use the PCA analysis from the sklearn library to get a set
of “component” vectors, where the vectors are orthogonal to each other
and explain the maximum variance of the samples in each prefix of the
list. Components in PCA are bidirectional (they can come out of the
analysis in either reflection, and both are equally correct), so next
they flip any component vectors that are pointing more towards the
negative samples than the positive samples. Then, they take the first
component, the most important one, and use it as their reading vector.

Our method for prompt generation didn’t admit contrastive pairs like
in the previous methods, but instead just a bunch of unconnected
positive and negative examples. So instead of doing PCA on contrast
vectors, we averaged the positive examples and the negative examples,
and then took the difference of the averages as our base reading
vector. This is called "mass mean probing" in the literature, and
empirically has been shown to generalize better in high dimensional
space than trying to learn a linear model through logistic
regression.^[see the appendix section "Mass Mean Probing vs Linear
Regression" for more on this]

In this reading vector, the impact of each layer based on the
magnitude of difference in that layer, instead of separate a notion of
how "important" that layer is to differentiating positive and negative
examples. So we decided to try a few different methods of normalizing
these layers to improve their overall accuracy as a linear model:

* No normalization; just the projection across the average difference.
* Normalizing each layers vector to a uniform length
* Dividing by the average amount that each layer activates on the positives samples
* Dividing by the average absolute amount that each layer activates on the positive samples
* Dividing by the square root of the average of squares of layer activations

And we found that no normalization actually did the best of all three
scaling methods. In domains like this one where we have a lot less
training data points then dimensions, what techniques will generalize
well to the test data can be hard to predict.


# Appendix

## Optionality In Python

To see how Optionality appears in Python, Let’s look at an example
program in Python that uses optionality:

```python
class User:
    def __init__(self, name: str, email: Optional[str]) -> None:
    	 self.name = name
        self.email = email

def get_user_email(user: Optional[User]) -> Optional[str]:
    if user is not None and user.email is not None:
        return user.email
    else:
    	  return None
```

In the `get_user_email` function above, we can see from the type
signature that it takes a optional User value, and returns an optional
string. The first thing the function does is check if the input `user`
is None or not. This program was actually generated by o1-mini, so we
can already see that the model understands that the user object is
optional, and that it needs to be checked for None-ness before
anything else can be done.

We can say that there are five variable “occurances” in the program,
each of which can be either optional or not. There’s the first `user`
in the if statement, the second `user` to the right of the `and` in
`user.email`, there’s the `user.email` itself, the `user` on the
second line, and finally the `user.email` on the second line. If we
use Python’s typechecker, mypy, to check the types of each of these
occurrences, we find that they have type `Optional[User]`, `User`,
`Optional[str]`, `User`, and `str` respectively. That is, the first
and third are optional, and the rest are not.


## Detailed High-Level Optionality Test Results

### Different Models

You can see in Figure 1 that the smallest three models don’t pass any
test. After that, the trend line for tests passed goes upwards, but
it’s not monotonic: Pythia 410m passes only one test, while Pythia
160m passes three, and Pythia 6.9b passes the most tests, with 9,
while Pythia 12b only passes 7. For instance, given the partial code:

*Test 3*
```python
def main(x: int) -> None:
  if x > 0:
    value = "*" * x
  else:
    value = None

  x = process_value(value) + 1
  print(x)

def process_value(value):
```
Pythia 6.9b completes `process_value` as:
```python
def process_value(value):
  if value is None:
    return 0
  elif isinstance(value, str):
    return int(value)
  ...
```
While Pythia 12b completes it as:
```python
def process_value(value):
  return value
```

The code generated by Pythia 6.9b properly handles values of both
NoneType and str and always returns an int, whereas the code generated
by Pythia 12b is the identify function, returning None when the input
is None and returning a string when the input is a string. Neither of
these cases is correct, as the main function expects this to return a
Number that can be added to one.

### Different Sizes

We say in Figure 2 that while the model generally gets better at
passing these tests during training, the performance is not always
increasing.  Zooming in on a particular test, we can see what this
looks like. When asked to complete this code:

*Test 12*
```python
def handle_value(value, guard):
  if guard:
    return count_os("Foobar") * 2
  else:
    return count_os(value) // 2

def main(x: int) -> None:
  if x > 0:
    value = "*" * x
  else:
    value = None

  print(handle_value(value, x < 10))

def count_os(value):
```

Pythia 6.9b at training step 104000 produces the following definition
of `count_os`:

```python
def count_os(value):
  if value is None:
    return 1
  elif isinstance(value, str):
    return len(value)
...
```

While 1000 steps later, it produces a very different definition:

```python
def count_os(value):
  return len([s for s in os.listdir(os.path.join(os.getcwd(), value)) if s.start ...
```

While the first definition handles value being None or a string, the
second definition not only assumes it is a string but that it is a
name of a folder in the current directory. In some sense the model
“knows” that the value parameter is Optional at step 104000, but
“forgets” it during further training. It regains the ability to pass
the test at several points during training, but by the end of
training, it’s back to treating `value` as if it was always a string.

### Common Mistakes

As expected, type annotations are particularly difficult for these
models. When asked to complete the type of get_square in the following
code, no model in the Pythia series can successfully output the
Optional argument type:

*Test 5*
```python
def program_48() -> None:
  number: Optional[int] = None
  square = get_square(number)
  if square is not None:
    print(f"Square of the number is {square}")
  else:
    print("No number provided to square")

def get_square(number:
```

These models also find it much easier to deal with a list that
contains some None elements, than to deal with an atomic value that
might be None. Pythia 6.9b consistently passes this test in the
second half of training:

*Test 2*
```python
from typing import Optional

def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  print(positive_numbers(some_numbers))

def positive_numbers(numbers: list[Optional[int]]) -> list[int]:
  result: list[int] = []
  for num in numbers:
```

But is much more challenged by this code:

*Test 3*
```python
def main(x: int) -> None:
  if x > 0:
    value = "*" * x
  else:
    value = None

  x = process_value(value) + 1
  print(x)

def process_value(value):
```

, intermittently being unable to complete it in a type-safe way up,
including in the second-to-last training step. When another level of
function indirection is added, the model becomes much better at
completing it correctly; Pythia 6.9b consistently completes the
following after step 93000:

*Test 4*
```python
def handle_value(value, guard):
  if guard:
    return process_value("Foobar") + 1
  else:
    return process_value(value) + 1
def main(x: int) -> None:
  if x > 0:
    value = "*" * x
  else:
    value = None

  x = handle_value(value, x < 10)
  print(x)

def process_value(value):
```
The names of functions are highly influential in the models
understanding of their type semantics. When test 3 is changed so that
`process_value` is instead called `count_chars`, Pythia 6.9b becomes
unable to correctly complete it on any revision; it likely has a bias
from its training data that functions called `count_chars` always take
non-optional strings. Similarly, when test 4 is changed so that
process_values becomes string_complexity, it goes from consistently
passing to almost always failing.

## Mass Mean Probing vs Linear Regression

We were initially very surprised to find that mass means probing would
perform better than linear regression. After all, linear regression is
a much more powerful technique for fitting data. And mass means
probing can be seen as giving the direction of best fit in each
dimension independently, without considering other dimensions. The
more dimensions you consider at one time, the better your model fit
can be. But repeatedly in our data, we found that mass means probing
outperformed linear regression on the test data.